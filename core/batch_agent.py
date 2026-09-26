"""
Batch processing agent - fetches menus from multiple restaurants with error handling.
Supports parallel processing with configurable concurrency.
"""
import os
import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from tools.search_tool import search_restaurants_nearby
from tools.menu_tool import get_restaurant_menu
from tools.filter_tool import filter_menu_by_user_profile


class BatchMenuProcessor:
    """Processes menus from multiple restaurants in batch with error handling."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.batch_size = int(os.getenv("MENU_BATCH_SIZE", "5"))
        self.concurrency = int(os.getenv("MENU_FETCH_CONCURRENCY", "3"))

    def _fetch_single_menu(self, restaurant: Dict[str, Any], index: int, total: int) -> Dict[str, Any]:
        """
        Fetch menu for a single restaurant (used by parallel executor).

        Args:
            restaurant: Restaurant data
            index: Current index (for logging)
            total: Total count (for logging)

        Returns:
            Result dict with success status
        """
        restaurant_name = restaurant.get("name", "Unknown")
        restaurant_url = restaurant.get("website", "")

        if not restaurant_url:
            self.logger.warning(f"[{index}/{total}] {restaurant_name}: No website URL - skipping")
            return {
                "success": False,
                "restaurant": restaurant_name,
                "error": "No website URL"
            }

        try:
            self.logger.info(f"[{index}/{total}] Fetching menu from {restaurant_name}...")

            # Fetch menu using the tool
            menu_result = get_restaurant_menu.invoke({
                "restaurant_name": restaurant_name,
                "restaurant_url": restaurant_url,
                "force_fetch": False
            })

            # Check if successful
            if isinstance(menu_result, dict):
                items = menu_result.get("items", [])
                if items:
                    self.logger.info(f"✓ {restaurant_name}: {len(items)} items")
                    return {
                        "success": True,
                        "menu": {
                            **menu_result,
                            "restaurant_info": restaurant
                        }
                    }
                else:
                    error_msg = menu_result.get("error", "No items found")
                    self.logger.warning(f"✗ {restaurant_name}: {error_msg}")
                    return {
                        "success": False,
                        "restaurant": restaurant_name,
                        "error": error_msg
                    }
            else:
                self.logger.warning(f"✗ {restaurant_name}: Invalid result format")
                return {
                    "success": False,
                    "restaurant": restaurant_name,
                    "error": "Invalid result format"
                }

        except Exception as e:
            self.logger.error(f"✗ {restaurant_name}: Exception - {e}")
            return {
                "success": False,
                "restaurant": restaurant_name,
                "error": str(e)
            }

    def fetch_all_menus(
        self,
        restaurants: List[Dict[str, Any]],
        max_restaurants: int = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch menus from all restaurants IN PARALLEL with error handling.

        Args:
            restaurants: List of restaurant dicts from search results
            max_restaurants: Maximum number to process (default: batch_size)

        Returns:
            List of successful menu fetches with items
        """
        # Filter restaurants that have websites BEFORE processing
        restaurants_with_websites = [
            r for r in restaurants if r.get("website")
        ]

        if not restaurants_with_websites:
            self.logger.warning(f"None of the {len(restaurants)} restaurants have websites - cannot fetch menus")
            return []

        self.logger.info(f"Filtered {len(restaurants_with_websites)}/{len(restaurants)} restaurants with websites")

        max_restaurants = max_restaurants or self.batch_size
        to_process = restaurants_with_websites[:max_restaurants]

        self.logger.info(f"Batch processing {len(to_process)} restaurants with concurrency={self.concurrency}...")

        successful_menus = []
        errors = []

        # Visual progress indicator
        from rich.console import Console
        console = Console()

        # Process in parallel with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            # Submit all tasks
            future_to_restaurant = {
                executor.submit(self._fetch_single_menu, restaurant, i, len(to_process)): restaurant
                for i, restaurant in enumerate(to_process, 1)
            }

            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_restaurant):
                result = future.result()
                completed += 1

                if result.get("success"):
                    restaurant_name = result["menu"].get("restaurant", "Unknown")
                    items_count = len(result["menu"].get("items", []))
                    console.print(f"[green]  ✓ {restaurant_name}: {items_count} items[/green] ({completed}/{len(to_process)})")
                    successful_menus.append(result["menu"])
                else:
                    restaurant_name = result.get("restaurant", "Unknown")
                    error = result.get("error", "Unknown error")
                    console.print(f"[yellow]  ✗ {restaurant_name}: {error}[/yellow] ({completed}/{len(to_process)})")
                    errors.append({
                        "restaurant": result.get("restaurant"),
                        "error": result.get("error")
                    })

        self.logger.info(f"Batch complete: {len(successful_menus)} successful, {len(errors)} failed")

        return successful_menus

    def filter_combined_menus(
        self,
        menus: List[Dict[str, Any]],
        allergies: List[str],
        dietary_restrictions: List[str],
        max_price: float
    ) -> Dict[str, Any]:
        """
        Combine all menu items and filter them.

        Args:
            menus: List of menu results with items
            allergies: User allergies
            dietary_restrictions: User restrictions
            max_price: Max price per item

        Returns:
            Filtered results with restaurant info preserved
        """
        # Combine all items from all restaurants
        all_items = []
        restaurant_map = {}  # Track which items came from which restaurant

        for menu in menus:
            restaurant_name = menu.get("restaurant", "Unknown")
            items = menu.get("items", [])

            for item in items:
                # Add restaurant reference to each item
                item_with_source = {
                    **item,
                    "_restaurant": restaurant_name,
                    "_restaurant_info": menu.get("restaurant_info", {})
                }
                all_items.append(item_with_source)

        self.logger.info(f"Combined {len(all_items)} items from {len(menus)} restaurants")

        if not all_items:
            return {
                "filtered_items": [],
                "removed_count": 0,
                "passed_count": 0,
                "restaurants_processed": len(menus)
            }

        # Filter combined items
        try:
            filter_result = filter_menu_by_user_profile.invoke({
                "menu_items": all_items,
                "allergies": allergies,
                "dietary_restrictions": dietary_restrictions,
                "max_price": max_price
            })

            self.logger.info(f"Filter result: {filter_result.get('passed_count', 0)} items passed")

            return {
                **filter_result,
                "restaurants_processed": len(menus)
            }

        except Exception as e:
            self.logger.error(f"Filter failed: {e}")
            return {
                "filtered_items": [],
                "removed_count": 0,
                "passed_count": 0,
                "restaurants_processed": len(menus),
                "error": str(e)
            }
