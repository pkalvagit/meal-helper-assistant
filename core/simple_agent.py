"""
Simplified LangChain agent - compatible with all LangChain versions.
Uses manual tool calling loop instead of AgentExecutor.
"""
from typing import Optional, Dict, Any, List
import json
import logging
import os

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_community.chat_message_histories import ChatMessageHistory

from core.llm_factory import get_llm_factory
from core.guardrails import RestaurantGuardrail
from core.models import UserProfile, AgentResponse
from core.logger import log_tool_call, log_tool_result, log_error
from core.stats_logger import StatsLogger
from core.batch_agent import BatchMenuProcessor
from tools.search_tool import search_restaurants_nearby, search_restaurants_by_query
from tools.menu_tool import (
    get_restaurant_menu,
    check_menu_cache_status,
    extract_menu_from_text,
    set_stats_logger
)
from tools.filter_tool import filter_menu_by_user_profile, rank_items_by_preferences


class SimpleMealHelperAgent:
    """
    Simplified agent using manual tool calling loop.
    Compatible with all LangChain versions (0.2, 0.3, 1.0+).
    """

    def __init__(
        self,
        user_profile: Optional[UserProfile] = None,
        primary_provider: Optional[str] = None,
        guardrail_provider: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        stats_logger: Optional[StatsLogger] = None
    ):
        """Initialize agent with LLMs from config."""
        self.user_profile = user_profile
        self.factory = get_llm_factory()
        self.logger = logger or logging.getLogger("meal-helper")
        self.stats_logger = stats_logger or StatsLogger()
        self.current_query = ""  # Track current user query for recommendations

        # Get LLMs
        self.llm = self.factory.get_llm("primary", provider=primary_provider)
        self.guardrail = RestaurantGuardrail(provider=guardrail_provider)

        # Track active providers
        primary_config = self.factory.config["primary"]
        self.primary_provider = primary_provider or primary_config["provider"]
        self.primary_model = primary_config[self.primary_provider]["model"]

        self.logger.info(f"Agent initialized: {self.primary_provider} ({self.primary_model})")

        # Set stats logger for menu tools
        set_stats_logger(self.stats_logger)

        # Batch processor for fetching multiple menus
        self.batch_processor = BatchMenuProcessor(self.logger)

        # Message history
        self.message_history = ChatMessageHistory()

        # Available tools (kept for compatibility)
        self.tools = {
            "search_restaurants_nearby": search_restaurants_nearby,
            "search_restaurants_by_query": search_restaurants_by_query,
            "get_restaurant_menu": get_restaurant_menu,
            "check_menu_cache_status": check_menu_cache_status,
            "extract_menu_from_text": extract_menu_from_text,
            "filter_menu_by_user_profile": filter_menu_by_user_profile,
            "rank_items_by_preferences": rank_items_by_preferences,
        }

        # Load configuration from environment
        self.search_radius = int(os.getenv("SEARCH_RADIUS_METERS", "5000"))
        self.batch_size = int(os.getenv("MENU_BATCH_SIZE", "5"))

    def process_meal_request(
        self,
        query: str,
        lat: float,
        lng: float
    ) -> Dict[str, Any]:
        """
        Execute the complete workflow: search → fetch all menus → filter.

        This is the CORRECT workflow pattern:
        1. Search for restaurants
        2. Fetch menus from ALL restaurants (with error handling)
        3. Filter combined results
        4. Return to LLM for recommendation formatting

        Args:
            query: Search query (e.g., "biryani", "burger")
            lat: Latitude
            lng: Longitude

        Returns:
            {
                "restaurants": [...],  # Restaurants with menus
                "filtered_items": [...],  # Items that passed filters
                "stats": {...}
            }
        """
        from rich.console import Console
        console = Console()

        try:
            # Step 1: Search for restaurants
            console.print(f"[cyan]🔍 Searching for {query}...[/cyan]")
            self.logger.info(f"Searching for: {query}")

            search_results = search_restaurants_by_query.invoke({
                "query": query,
                "lat": lat,
                "lng": lng,
                "radius": self.search_radius,
                "max_results": int(os.getenv("SEARCH_MAX_RESULTS", "20"))
            })

            if not search_results or len(search_results) == 0:
                return {
                    "success": False,
                    "error": "No restaurants found",
                    "restaurants": [],
                    "filtered_items": []
                }

            self.logger.info(f"Found {len(search_results)} restaurants")

            # Step 2: Batch fetch ALL menus (with error handling)
            console.print(f"[yellow]📋 Fetching menus from {min(len(search_results), self.batch_size)} restaurants...[/yellow]")

            menus = self.batch_processor.fetch_all_menus(
                search_results,
                max_restaurants=self.batch_size
            )

            if not menus:
                return {
                    "success": False,
                    "error": "Could not fetch any menus",
                    "restaurants": search_results,
                    "filtered_items": []
                }

            # Step 3: Filter combined menus
            console.print(f"[green]✓ Filtering menu items...[/green]")

            filter_result = self.batch_processor.filter_combined_menus(
                menus,
                allergies=self.user_profile.allergies if self.user_profile else [],
                dietary_restrictions=self.user_profile.dietary_restrictions if self.user_profile else [],
                max_price=self.user_profile.budget.max_per_meal if self.user_profile else 100.0
            )

            return {
                "success": True,
                "restaurants": menus,
                "filtered_items": filter_result.get("filtered_items", []),
                "stats": {
                    "searched": len(search_results),
                    "processed": len(menus),
                    "total_items": sum(len(m.get("items", [])) for m in menus),
                    "filtered_items": len(filter_result.get("filtered_items", [])),
                    "removed": filter_result.get("removed_count", 0)
                }
            }

        except Exception as e:
            self.logger.error(f"Error in process_meal_request: {e}")
            return {
                "success": False,
                "error": str(e),
                "restaurants": [],
                "filtered_items": []
            }

    def _build_system_prompt(self) -> str:
        """Build system prompt with user profile."""
        base_prompt = """You are a helpful restaurant recommendation assistant.
You help users find restaurants and menu items that match their preferences and dietary needs.

⚠️ CRITICAL: When user asks for food recommendations (e.g., "find biryani near me"), you MUST:
1. Search for restaurants → get_restaurant_menu → filter → then respond
2. NEVER respond with just restaurant names - user needs actual menu items with prices
3. Search results alone DO NOT answer the user's question - fetch menus first!

Your capabilities:
1. Search for restaurants near a location
2. Get restaurant menus (check cache first)
3. Filter menu items by allergies, restrictions, and preferences
4. Rank items by user preferences
5. Provide detailed explanations and recommendations

IMPORTANT RULES:
- ALWAYS filter menu items by user's allergies BEFORE recommending
- Check menu cache before fetching (faster & cheaper)
- Provide natural, conversational responses
- Explain WHY you're recommending something
- If no suitable items found, suggest alternatives
- BE PROACTIVE: Don't ask for clarification unless there's a DIRECT conflict
  * ONLY ask for clarification if user specifically requests a restricted item (e.g., "beef burger" when they have "no_beef")
  * For generic queries like "burger" or "biryani", just search and let the filter tools remove incompatible items
  * Trust your tools - they will automatically filter out allergens and restrictions

CRITICAL: NEVER HALLUCINATE MENU ITEMS
- If get_restaurant_menu returns empty items ({"items": []}), DO NOT recommend anything from that restaurant
- DO NOT make up generic menu items like "chicken sandwich - price may vary"
- DO NOT suggest "it's worth asking for X" without actual menu data
- ONLY recommend specific items you actually fetched from the menu
- If all restaurants return empty menus, tell the user "I couldn't fetch any menu data" and suggest trying other restaurants

Available tools and COMPLETE WORKFLOW:

⚠️ CRITICAL WORKFLOW RULE ⚠️
NEVER respond to the user after search_restaurants_by_query without first fetching menus!
You MUST call get_restaurant_menu immediately after search_restaurants_by_query.
DO NOT return intermediate results like "I found these restaurants" - fetch menus first!

WORKFLOW: Search → Get Menus → Filter → Recommend
(Execute ALL steps before responding to user)

Step 1: SEARCH - Find restaurants
Tool: search_restaurants_by_query
Returns: [{"name": "Restaurant Name", "website": "https://example.com", "address": "...", "rating": 4.5}]
⚠️ DO NOT respond to user yet - continue to Step 2!

Step 2: GET MENUS - IMMEDIATELY call get_restaurant_menu for top 2-3 restaurants
Tool: get_restaurant_menu (call this for EACH restaurant with a website)
CRITICAL: Extract "website" field from search results → use as "restaurant_url"
Example call 1: {"tool": "get_restaurant_menu", "arguments": {"restaurant_name": "Masti", "restaurant_url": "http://www.mastiusa.com/"}}
Example call 2: {"tool": "get_restaurant_menu", "arguments": {"restaurant_name": "Restaurant 2", "restaurant_url": "http://example2.com/"}}
Returns: {"items": [{"name": "Dish", "price": "$12.99", "description": "..."}]}
⚠️ DO NOT respond to user yet - continue to Step 3!

Step 3: FILTER - Apply user constraints automatically
Tool: filter_menu_by_user_profile
Combine ALL menu items from Step 2, then filter
Example: {"tool": "filter_menu_by_user_profile", "arguments": {"menu_items": [...all items...], "allergies": ["peanuts", "shellfish"], "dietary_restrictions": ["no_beef", "no_pork"], "max_price": 25.0}}
Returns: Filtered list of safe items

Step 4: RECOMMEND - NOW you can respond to user with formatted recommendations

CRITICAL EXECUTION RULES:
1. NEVER respond after search_restaurants_by_query - always fetch menus first
2. Fetch menus for at least 2 restaurants (if they have websites)
3. If ALL menu fetches fail, THEN tell user "couldn't fetch menu data"
4. Complete Steps 1-3 in ONE workflow run before giving final answer

FINAL RESPONSE FORMAT:
When providing recommendations, ALWAYS include for each restaurant:
1. Restaurant name (prominently displayed)
2. Full address from search results
3. Google Maps URL (use address with spaces replaced by +): https://www.google.com/maps/search/?api=1&query=ADDRESS+WITH+PLUS+SIGNS
4. Restaurant website (if available)
5. Rating (if available)
6. Then list the recommended menu items

Example format:
## Restaurant Name ⭐ 4.5
📍 **Address:** 1234 Main St, City, State ZIP
🗺️ **Google Maps:** https://www.google.com/maps/search/?api=1&query=1234+Main+St,+City,+State+ZIP
🌐 **Website:** https://example.com

**Recommended Items:**
1. Dish Name — $Price
   • Description
2. Dish Name 2 — $Price
   • Description

TOOL CALLING FORMAT:
When you need to use a tool, respond with ONLY the JSON (no extra text):
{
  "tool": "tool_name",
  "arguments": {"arg1": value1, "arg2": value2},
  "reasoning": "Why you're calling this tool"
}

⚠️ MINIMUM TOOL CHAIN FOR FOOD RECOMMENDATIONS ⚠️
If user asks for food recommendations, you MUST call at least these tools IN SEQUENCE:
1. search_restaurants_by_query (find restaurants)
2. get_restaurant_menu (for at least 1 restaurant from step 1)
3. filter_menu_by_user_profile (apply constraints)

EXAMPLE OF CORRECT WORKFLOW:
User: "find biryani under $25 near me"

Step 1 - Your response:
{"tool": "search_restaurants_by_query", "arguments": {"query": "biryani", "lat": 38.9586, "lng": -77.357, "radius": 5000, "max_results": 20}, "reasoning": "Search for biryani restaurants"}

[Tool returns: [{"name": "Masti", "website": "http://mastiusa.com", ...}]]

Step 2 - Your NEXT response (NOT text to user!):
{"tool": "get_restaurant_menu", "arguments": {"restaurant_name": "Masti", "restaurant_url": "http://mastiusa.com"}, "reasoning": "Fetch menu to get actual items and prices"}

[Tool returns: {"items": [{"name": "Chicken Biryani", "price": "$16.99", ...}]}]

Step 3 - Your NEXT response:
{"tool": "filter_menu_by_user_profile", "arguments": {"menu_items": [...], "allergies": ["peanuts"], "dietary_restrictions": ["no_beef"], "max_price": 25.0}, "reasoning": "Filter for user constraints"}

[Tool returns: filtered items]

Step 4 - NOW respond to user with formatted recommendations

DO NOT skip to Step 4 after Step 1! Always complete Steps 1-3 in sequence."""

        if self.user_profile:
            profile_info = f"""

USER PROFILE:
Name: {self.user_profile.name}
Allergies: {', '.join(self.user_profile.allergies) if self.user_profile.allergies else 'None'}
Dietary Restrictions: {', '.join(self.user_profile.dietary_restrictions) if self.user_profile.dietary_restrictions else 'None'}
Budget: ${self.user_profile.budget.max_per_meal} per meal
Preferences: {self.user_profile.preferences}
Default Location: {self.user_profile.location if self.user_profile.location else 'Not set'}

CRITICAL: You MUST filter out items containing: {', '.join(self.user_profile.allergies)}
This is a safety requirement - never recommend items with these allergens."""

            return base_prompt + profile_info

        return base_prompt

    def _print_progress(self, tool_name: str, arguments: Dict[str, Any]):
        """Print user-friendly progress indicator."""
        from rich.console import Console
        console = Console()

        if tool_name == "search_restaurants_nearby":
            cuisine = arguments.get("cuisine", arguments.get("query", "restaurants"))
            console.print(f"[cyan]🔍 Searching for {cuisine}...[/cyan]")
        elif tool_name == "search_restaurants_by_query":
            query = arguments.get("query", "restaurants")
            console.print(f"[cyan]🔍 Searching: {query}...[/cyan]")
        elif tool_name == "get_restaurant_menu":
            restaurant = arguments.get("restaurant_name", "restaurant")
            console.print(f"[yellow]📋 Fetching menu from {restaurant}...[/yellow]")
        elif tool_name == "filter_menu_by_user_profile":
            count = len(arguments.get("menu_items", []))
            console.print(f"[green]✓ Filtering {count} menu items...[/green]")
        elif tool_name == "rank_items_by_preferences":
            console.print(f"[blue]⭐ Ranking by preferences...[/blue]")

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool and return result."""
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            tool = self.tools[tool_name]
            result = tool.invoke(arguments)

            # Track tool results for recommendation logging
            if hasattr(self, '_session_data'):
                if tool_name in ["search_restaurants_nearby", "search_restaurants_by_query"]:
                    if isinstance(result, list) and result:
                        self._session_data["restaurants_searched"].extend(result)
                elif tool_name == "get_restaurant_menu":
                    if isinstance(result, dict) and result.get("items"):
                        self._session_data["menus_fetched"].append(result)
                elif tool_name == "filter_menu_by_user_profile":
                    if isinstance(result, list) and result:
                        self._session_data["items_filtered"] = result

            return result
        except Exception as e:
            return {"error": str(e)}

    def chat(self, user_message: str, max_iterations: int = 10) -> AgentResponse:
        """
        Main chat interface - SIMPLIFIED WORKFLOW.

        Args:
            user_message: User's natural language query
            max_iterations: Not used anymore (kept for compatibility)

        Returns:
            AgentResponse with recommendations and metadata
        """
        # Store current query
        self.current_query = user_message

        # Step 1: Guardrail check (skip for short follow-ups)
        skip_guardrail = (
            len(self.message_history.messages) > 0 and
            len(user_message.strip()) < 50
        )

        guardrail_cost = 0.0

        if not skip_guardrail:
            guardrail_result = self.guardrail.check_query(
                user_message,
                self.user_profile
            )

            if not guardrail_result.is_valid:
                return AgentResponse(
                    success=False,
                    message=guardrail_result.reason,
                    cost=guardrail_result.cost
                )
            guardrail_cost = guardrail_result.cost

            # Extract query intent
            intent = guardrail_result.intent
        else:
            intent = None

        # Step 2: Execute batch workflow if this is a meal request
        if self.user_profile and self.user_profile.location:
            # User has location - execute full workflow
            # Support both formats: latitude/longitude or default_lat/default_lng
            lat = (self.user_profile.location.get("latitude") or
                   self.user_profile.location.get("default_lat") or
                   self.user_profile.location.get("lat"))
            lng = (self.user_profile.location.get("longitude") or
                   self.user_profile.location.get("default_lng") or
                   self.user_profile.location.get("lng"))

            if lat and lng:
                self.logger.info("Executing batch workflow")

                # Extract search query from user message (use intent if available)
                search_query = user_message  # Simplified - could parse better

                # Execute full workflow
                result = self.process_meal_request(search_query, lat, lng)

                if result.get("success"):
                    # Format results with LLM
                    formatted_response = self._format_recommendations(result)

                    # Save to history
                    self.message_history.add_user_message(user_message)
                    self.message_history.add_ai_message(formatted_response)

                    return AgentResponse(
                        success=True,
                        message=formatted_response,
                        metadata={
                            "stats": result.get("stats", {}),
                            "restaurants_count": len(result.get("restaurants", []))
                        },
                        cost=guardrail_cost + 0.03  # Estimate
                    )
                else:
                    error_msg = result.get("error", "Could not process request")
                    return AgentResponse(
                        success=False,
                        message=f"I encountered an issue: {error_msg}",
                        cost=guardrail_cost
                    )

        # Fallback: No location or different request type - use old loop
        return self._chat_with_tools(user_message, guardrail_cost, max_iterations)

    def _chat_with_tools(self, user_message: str, guardrail_cost: float, max_iterations: int) -> AgentResponse:
        """
        Fallback: Original tool calling loop for non-standard requests.
        """
        self._session_data = {
            "restaurants_searched": [],
            "menus_fetched": [],
            "items_filtered": []
        }

        # Step 2: Build messages
        messages = [SystemMessage(content=self._build_system_prompt())]

        # Add conversation history
        for msg in self.message_history.messages:
            messages.append(msg)

        # Add user message
        messages.append(HumanMessage(content=user_message))

        # Step 3: Tool calling loop
        iterations = 0

        while iterations < max_iterations:
            try:
                # Get LLM response
                response = self.llm.invoke(messages)
                response_text = response.content

                # Check if response contains tool call (JSON)
                is_tool = self._is_tool_call(response_text)

                if is_tool:
                    self.logger.debug(f"Detected tool call, response length: {len(response_text)}, starts with: {response_text[:100]}")
                    tool_call = self._parse_tool_call(response_text)

                    if not tool_call:
                        # Log first 2000 chars for debugging
                        self.logger.error(f"Failed to parse tool call. Response: {response_text[:2000]}")

                    if tool_call:
                        tool_name = tool_call['tool']
                        tool_args = tool_call['arguments']
                        reasoning = tool_call.get('reasoning', '')

                        # Log to file (verbose)
                        log_tool_call(self.logger, tool_name, tool_args)

                        # User-friendly progress indicator
                        self._print_progress(tool_name, tool_args)
                    else:
                        # Parsing failed - likely the LLM made a mistake
                        # Log the issue and return an error
                        self.logger.error(f"Failed to parse tool call from response: {response_text[:500]}")
                        return AgentResponse(
                            success=False,
                            message="I tried to use a tool but made a formatting error. Please try your request again.",
                            cost=guardrail_cost + 0.02 * (iterations + 1)
                        )

                        # Execute tool
                        result = self._execute_tool(tool_name, tool_args)

                        # Log result
                        success = not ("error" in result if isinstance(result, dict) else False)
                        result_summary = f"{len(result)} items" if isinstance(result, list) else str(result)[:100]
                        log_tool_result(self.logger, tool_name, success, result_summary)

                        # Add tool result to messages
                        messages.append(AIMessage(content=response_text))

                        # Special handling: force workflow continuation
                        if tool_name in ["search_restaurants_nearby", "search_restaurants_by_query"]:
                            if isinstance(result, list) and len(result) > 0 and result[0].get("website"):
                                # Add a directive to fetch menus
                                tool_result_message = f"""Tool result: {json.dumps(result, indent=2)}

IMPORTANT: You just found restaurants. The user asked for food recommendations, so you MUST now call get_restaurant_menu for at least one restaurant.
DO NOT respond with text. Your next response MUST be a tool call to get_restaurant_menu.
Use the "website" field from the search results as "restaurant_url"."""
                                messages.append(HumanMessage(content=tool_result_message))
                            else:
                                messages.append(HumanMessage(content=f"Tool result: {json.dumps(result, indent=2)}"))
                        elif tool_name == "get_restaurant_menu":
                            # After fetching menu, force filtering
                            if isinstance(result, dict) and result.get("items"):
                                tool_result_message = f"""Tool result: {json.dumps(result, indent=2)}

IMPORTANT: You just fetched a menu with {len(result['items'])} items. You MUST now call filter_menu_by_user_profile to apply dietary restrictions and budget constraints.
DO NOT respond with text. Your next response MUST be a tool call to filter_menu_by_user_profile.
Include ALL items from this menu in the menu_items argument."""
                                messages.append(HumanMessage(content=tool_result_message))
                            else:
                                messages.append(HumanMessage(content=f"Tool result: {json.dumps(result, indent=2)}"))
                        else:
                            messages.append(HumanMessage(content=f"Tool result: {json.dumps(result, indent=2)}"))

                        iterations += 1
                        continue

                # No tool call - final answer
                self.message_history.add_user_message(user_message)
                self.message_history.add_ai_message(response_text)

                # Log recommendations if we have menu items
                self._log_recommendations()

                return AgentResponse(
                    success=True,
                    message=response_text,
                    metadata={
                        "iterations": iterations,
                    },
                    cost=guardrail_cost + 0.02  # Estimate
                )

            except Exception as e:
                log_error(self.logger, e, "Agent chat loop error")
                return AgentResponse(
                    success=False,
                    message=f"Error: {str(e)}",
                    cost=guardrail_cost
                )

        # Max iterations reached
        return AgentResponse(
            success=False,
            message="Max iterations reached. Please try rephrasing your query.",
            cost=guardrail_cost + 0.02 * iterations  # Estimate
        )

    def _format_recommendations(self, result: Dict[str, Any]) -> str:
        """
        Format batch processing results into user-friendly recommendations.

        Args:
            result: Result from process_meal_request

        Returns:
            Formatted markdown text
        """
        filtered_items = result.get("filtered_items", [])
        restaurants = result.get("restaurants", [])
        stats = result.get("stats", {})

        if not filtered_items:
            return f"I searched {stats.get('searched', 0)} restaurants and fetched {stats.get('processed', 0)} menus, but couldn't find any items that match your criteria (under ${self.user_profile.budget.max_per_meal if self.user_profile else 20}, no {', '.join(self.user_profile.allergies if self.user_profile else [])} allergies, and no {', '.join(self.user_profile.dietary_restrictions if self.user_profile else [])}).\n\nWould you like me to search with different criteria?"

        # Group items by restaurant
        by_restaurant = {}
        for item in filtered_items:
            rest_name = item.get("_restaurant", "Unknown")
            if rest_name not in by_restaurant:
                by_restaurant[rest_name] = []
            by_restaurant[rest_name].append(item)

        # Build response
        lines = []
        lines.append(f"I found **{len(filtered_items)} items** from **{len(by_restaurant)} restaurants** that match your criteria:\n")

        for rest_name, items in by_restaurant.items():
            # Find restaurant info
            rest_info = None
            for menu in restaurants:
                if menu.get("restaurant") == rest_name:
                    rest_info = menu.get("restaurant_info", {})
                    break

            if rest_info:
                address = rest_info.get("address", "")
                rating = rest_info.get("rating", "")
                website = rest_info.get("website", "")

                # Format restaurant header
                rating_str = f" ⭐ {rating}" if rating else ""
                lines.append(f"\n## {rest_name}{rating_str}")

                if address:
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"
                    lines.append(f"📍 **Address:** {address}")
                    lines.append(f"🗺️ **Google Maps:** {maps_url}")

                if website:
                    lines.append(f"🌐 **Website:** {website}")

                lines.append(f"\n**Recommended Items:** ({len(items)} items)")
            else:
                lines.append(f"\n## {rest_name}")
                lines.append(f"\n**Recommended Items:** ({len(items)} items)")

            # List items (limit to top 5 per restaurant)
            for i, item in enumerate(items[:5], 1):
                name = item.get("name", "Unknown")
                price = item.get("price", "")
                desc = item.get("description", "")

                lines.append(f"{i}. **{name}** — {price}")
                if desc and len(desc) < 200:
                    lines.append(f"   • {desc}")

            if len(items) > 5:
                lines.append(f"   *...and {len(items) - 5} more items*")

        # Add footer with stats
        lines.append(f"\n---")
        lines.append(f"*Searched {stats.get('searched', 0)} restaurants • Fetched {stats.get('processed', 0)} menus • Filtered {stats.get('total_items', 0)} items*")

        return "\n".join(lines)

    def _is_tool_call(self, text: str) -> bool:
        """Check if response contains a tool call (JSON can be anywhere in text)."""
        return '"tool"' in text and '"arguments"' in text

    def _parse_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse tool call JSON from response (handles text before/after JSON)."""
        try:
            text = text.strip()

            # Remove markdown code blocks if present
            if "```" in text:
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
                if json_match:
                    text = json_match.group(1).strip()

            # Try 1: Direct parse (for when response is just JSON)
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict) and "tool" in parsed and "arguments" in parsed:
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass

            # Try 2: Extract JSON using JSONDecoder (handles extra text)
            try:
                from json import JSONDecoder
                decoder = JSONDecoder()

                # Find the start of JSON
                start_idx = text.find('{')
                if start_idx != -1:
                    parsed, _ = decoder.raw_decode(text, start_idx)
                    if isinstance(parsed, dict) and "tool" in parsed and "arguments" in parsed:
                        return parsed
            except (json.JSONDecodeError, ValueError):
                pass

            # Try 3: Manual extraction - find JSON block
            import re
            # Look for {"tool":... pattern
            match = re.search(r'\{[^}]*"tool"[^}]*"arguments".*?\}(?:\})*', text, re.DOTALL)
            if match:
                candidate = match.group(0)

                # Extend to get complete JSON (handle nested objects)
                start = match.start()
                brace_count = 0
                in_string = False
                escape = False
                end = start

                for i in range(start, len(text)):
                    c = text[i]

                    if escape:
                        escape = False
                        continue
                    if c == '\\':
                        escape = True
                        continue
                    if c == '"' and not escape:
                        in_string = not in_string
                        continue

                    if not in_string:
                        if c == '{':
                            brace_count += 1
                        elif c == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end = i + 1
                                break

                if end > start:
                    candidate = text[start:end]
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict) and "tool" in parsed and "arguments" in parsed:
                            return parsed
                    except:
                        pass

            return None

        except Exception as e:
            self.logger.error(f"Exception in _parse_tool_call: {e}")
            self.logger.error(f"Text was: {text[:1000]}")
            return None

    def _log_recommendations(self):
        """Log final recommendations with restaurant and menu details."""
        if not hasattr(self, '_session_data') or not self._session_data.get("menus_fetched"):
            return

        # Get filtered items (or all items from menus if not filtered)
        items_to_log = self._session_data.get("items_filtered", [])

        # If we fetched menus but didn't filter, use all fetched items
        if not items_to_log and self._session_data.get("menus_fetched"):
            for menu in self._session_data["menus_fetched"]:
                items_to_log.extend(menu.get("items", []))

        # Only log if we have items
        if not items_to_log:
            return

        # Log for each restaurant that had menu items
        for menu_result in self._session_data["menus_fetched"]:
            restaurant_name = menu_result.get("restaurant", "Unknown")
            restaurant_url = menu_result.get("url", "")
            menu_items = menu_result.get("items", [])

            # Find matching restaurant info from search results
            restaurant_address = ""
            for rest in self._session_data.get("restaurants_searched", []):
                if isinstance(rest, dict) and rest.get("name") == restaurant_name:
                    restaurant_address = rest.get("address", "")
                    break

            # Only log if we have items
            if menu_items:
                self.stats_logger.log_recommendation(
                    restaurant_name=restaurant_name,
                    restaurant_address=restaurant_address,
                    restaurant_url=restaurant_url,
                    menu_items=menu_items[:10],  # Top 10 items
                    user_query=self.current_query,
                    filters_applied={
                        "allergies": self.user_profile.allergies if self.user_profile else [],
                        "dietary_restrictions": self.user_profile.dietary_restrictions if self.user_profile else [],
                        "max_price": self.user_profile.budget.max_per_meal if self.user_profile else None,
                        "preferences": self.user_profile.preferences if self.user_profile else {}
                    },
                    ranking_criteria="high_protein" if self.user_profile and self.user_profile.preferences.get("high_protein") else None
                )

    def reset_conversation(self):
        """Clear conversation history."""
        self.message_history.clear()
