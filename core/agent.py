"""
LangChain-based Meal Recommendation Agent.
Provider-agnostic: Claude (Opus/Sonnet/Haiku) OR OpenAI (GPT-4o/4-turbo/5.4-mini/5.4-nano).
"""
from typing import Optional, Dict, Any
from pathlib import Path

try:
    # LangChain 0.3+ imports
    from langchain.agents import AgentExecutor, create_react_agent
    from langchain import hub
    use_react = True
except ImportError:
    # Fallback to older API
    from langchain.agents import AgentExecutor, initialize_agent, AgentType
    use_react = False

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_community.chat_message_histories import ChatMessageHistory

from core.llm_factory import get_llm_factory
from core.guardrails import RestaurantGuardrail
from core.models import UserProfile, AgentResponse
from tools.search_tool import search_restaurants_nearby, search_restaurants_by_query
from tools.menu_tool import (
    get_restaurant_menu,
    check_menu_cache_status,
    extract_menu_from_text
)
from tools.filter_tool import filter_menu_by_user_profile, rank_items_by_preferences


class MealHelperAgent:
    """
    Main agent for restaurant recommendations.

    Fully flexible LLM selection:
    - Primary LLM: Claude (Opus/Sonnet/Haiku) OR OpenAI (GPT-4o/4-turbo/5.4-mini/5.4-nano)
    - Guardrail LLM: Independent config (can mix Claude + OpenAI)
    - Configured via config/llm_config.yaml
    """

    def __init__(
        self,
        user_profile: Optional[UserProfile] = None,
        primary_provider: Optional[str] = None,
        guardrail_provider: Optional[str] = None
    ):
        """
        Initialize agent with LLMs from config.

        Args:
            user_profile: User dietary profile
            primary_provider: Override primary LLM provider ("claude" or "openai")
            guardrail_provider: Override guardrail LLM provider
        """
        self.user_profile = user_profile
        self.factory = get_llm_factory()

        # Get LLMs (respects config or overrides)
        self.llm = self.factory.get_llm("primary", provider=primary_provider)
        self.guardrail = RestaurantGuardrail(provider=guardrail_provider)

        # Track active providers
        primary_config = self.factory.config["primary"]
        self.primary_provider = primary_provider or primary_config["provider"]
        self.primary_model = primary_config[self.primary_provider]["model"]

        print(f"[Agent] Primary LLM: {self.primary_provider} ({self.primary_model})")

        # Message history for conversation
        self.message_history = ChatMessageHistory()

        # Create agent
        self.agent = self._create_agent()
        self.agent_executor = self._create_executor()

    def _create_agent(self):
        """Create LangChain agent with tools."""
        tools = [
            search_restaurants_nearby,
            search_restaurants_by_query,
            get_restaurant_menu,
            check_menu_cache_status,
            extract_menu_from_text,
            filter_menu_by_user_profile,
            rank_items_by_preferences,
        ]

        # Store tools for executor
        self.tools = tools

        # Build system prompt
        system_prompt = self._build_system_prompt()

        # Create prompt template
        if use_react:
            # Use ReAct agent for LangChain 0.3+
            try:
                # Try to get hwchase17/react prompt from hub
                prompt = hub.pull("hwchase17/react")
            except:
                # Fallback to manual prompt
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", "{input}"),
                    MessagesPlaceholder(variable_name="agent_scratchpad"),
                ])

            return create_react_agent(self.llm, tools, prompt)
        else:
            # Use older API
            return None  # Will use initialize_agent in executor

    def _build_system_prompt(self) -> str:
        """Build system prompt with user profile."""
        base_prompt = """You are a helpful restaurant recommendation assistant.
You help users find restaurants and menu items that match their preferences and dietary needs.

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
- If no suitable items found, suggest alternatives"""

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

    def _create_executor(self):
        """Create agent executor with error handling."""
        if use_react and self.agent:
            # Use new API
            return AgentExecutor(
                agent=self.agent,
                tools=self.tools,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=10,
                return_intermediate_steps=True,
            )
        else:
            # Use older initialize_agent API
            return initialize_agent(
                tools=self.tools,
                llm=self.llm,
                agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=10,
                return_intermediate_steps=True,
            )

    def chat(self, user_message: str) -> AgentResponse:
        """
        Main chat interface with guardrails.

        Args:
            user_message: User's natural language query

        Returns:
            AgentResponse with recommendations and metadata
        """
        # Step 1: Guardrail check
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

        # Step 2: Run agent
        try:
            result = self.agent_executor.invoke({
                "input": user_message,
                "chat_history": self.message_history.messages,
            })

            # Extract response
            output = result.get("output", "")
            intermediate_steps = result.get("intermediate_steps", [])

            # Update conversation history
            self.message_history.add_user_message(user_message)
            self.message_history.add_ai_message(output)

            # Calculate cost (simplified)
            total_cost = guardrail_result.cost + 0.02  # Estimate

            return AgentResponse(
                success=True,
                message=output,
                recommendations=[],  # Parsed from output if needed
                metadata={
                    "intent": guardrail_result.intent.dict() if guardrail_result.intent else {},
                    "steps": len(intermediate_steps),
                },
                cost=total_cost
            )

        except Exception as e:
            return AgentResponse(
                success=False,
                message=f"Error processing query: {str(e)}",
                cost=guardrail_result.cost
            )

    def reset_conversation(self):
        """Clear conversation history."""
        self.message_history.clear()
