"""
Stats logging for tracking menu extraction performance.
Logs per-restaurant stats and final recommendations for ground truth.
"""
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


class StatsLogger:
    """Track and log menu extraction stats and recommendations."""

    def __init__(self, log_dir: str = "logs"):
        """Initialize stats logger."""
        self.log_path = Path(__file__).parent.parent / log_dir
        self.log_path.mkdir(exist_ok=True)

        # Create session-specific log files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = timestamp

        # CSV for menu extraction stats
        self.stats_file = self.log_path / f"menu_stats_{timestamp}.csv"
        self._init_stats_csv()

        # JSON for recommendations (ground truth)
        self.recommendations_file = self.log_path / f"recommendations_{timestamp}.json"
        self.recommendations = []

    def _init_stats_csv(self):
        """Initialize CSV file with headers."""
        with open(self.stats_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp',
                'restaurant_name',
                'restaurant_url',
                'menu_url_found',
                'menu_url',
                'menu_url_type',
                'scraping_success',
                'md_file',
                'extraction_method',
                'items_found',
                'cached',
                'error'
            ])

    def log_menu_extraction(
        self,
        restaurant_name: str,
        restaurant_url: str,
        menu_url_found: bool,
        menu_url: Optional[str] = None,
        menu_url_type: Optional[str] = None,
        scraping_success: bool = False,
        md_file: Optional[str] = None,
        extraction_method: Optional[str] = None,
        items_found: int = 0,
        cached: bool = False,
        error: Optional[str] = None
    ):
        """
        Log menu extraction stats for a single restaurant.

        Args:
            restaurant_name: Name of restaurant
            restaurant_url: Restaurant website URL
            menu_url_found: Whether menu URL was found
            menu_url: The menu URL (if found)
            menu_url_type: Type of menu URL (anchor, pdf, etc)
            scraping_success: Whether scraping succeeded
            md_file: Path to scraped MD file
            extraction_method: Method used (pattern/llm_md/cached)
            items_found: Number of menu items extracted
            cached: Whether result was from cache
            error: Error message if failed
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(self.stats_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                restaurant_name,
                restaurant_url,
                menu_url_found,
                menu_url or '',
                menu_url_type or '',
                scraping_success,
                md_file or '',
                extraction_method or '',
                items_found,
                cached,
                error or ''
            ])

    def log_recommendation(
        self,
        restaurant_name: str,
        restaurant_address: str,
        restaurant_url: str,
        menu_items: List[Dict[str, Any]],
        user_query: str,
        filters_applied: Dict[str, Any],
        ranking_criteria: Optional[str] = None
    ):
        """
        Log final recommendations with full details for ground truth.

        Args:
            restaurant_name: Name of restaurant
            restaurant_address: Full address
            restaurant_url: Restaurant website
            menu_items: List of recommended menu items
            user_query: Original user query
            filters_applied: Filters that were applied (allergies, budget, etc)
            ranking_criteria: How items were ranked
        """
        recommendation = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session_id": self.session_id,
            "user_query": user_query,
            "restaurant": {
                "name": restaurant_name,
                "address": restaurant_address,
                "url": restaurant_url
            },
            "filters_applied": filters_applied,
            "ranking_criteria": ranking_criteria,
            "menu_items": menu_items,
            "total_items": len(menu_items)
        }

        self.recommendations.append(recommendation)

        # Write to file immediately
        with open(self.recommendations_file, 'w', encoding='utf-8') as f:
            json.dump({
                "session_id": self.session_id,
                "recommendations": self.recommendations
            }, f, indent=2, ensure_ascii=False)

    def get_stats_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics from current session.

        Returns:
            Dictionary with stats summary
        """
        if not self.stats_file.exists():
            return {}

        total = 0
        successful = 0
        cached = 0
        pattern_extracted = 0
        llm_extracted = 0
        failed = 0
        total_items = 0

        with open(self.stats_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                if row['cached'] == 'True':
                    cached += 1
                if row['items_found'] and int(row['items_found']) > 0:
                    successful += 1
                    total_items += int(row['items_found'])
                    if row['extraction_method'] == 'pattern':
                        pattern_extracted += 1
                    elif row['extraction_method'] and 'llm' in row['extraction_method']:
                        llm_extracted += 1
                else:
                    failed += 1

        return {
            "total_restaurants": total,
            "successful_extractions": successful,
            "failed_extractions": failed,
            "cached_results": cached,
            "pattern_extracted": pattern_extracted,
            "llm_extracted": llm_extracted,
            "total_items_found": total_items,
            "avg_items_per_restaurant": total_items / successful if successful > 0 else 0,
            "success_rate": f"{(successful / total * 100):.1f}%" if total > 0 else "0%"
        }

    def print_stats_summary(self):
        """Print stats summary to console."""
        summary = self.get_stats_summary()
        if not summary:
            print("\n[Stats] No data yet")
            return

        print("\n" + "="*60)
        print("📊 MENU EXTRACTION STATS SUMMARY")
        print("="*60)
        print(f"Total Restaurants:        {summary['total_restaurants']}")
        print(f"Successful Extractions:   {summary['successful_extractions']}")
        print(f"Failed Extractions:       {summary['failed_extractions']}")
        print(f"Success Rate:             {summary['success_rate']}")
        print(f"\nCached Results:           {summary['cached_results']}")
        print(f"Pattern Extracted (FREE): {summary['pattern_extracted']}")
        print(f"LLM Extracted:            {summary['llm_extracted']}")
        print(f"\nTotal Items Found:        {summary['total_items_found']}")
        print(f"Avg Items/Restaurant:     {summary['avg_items_per_restaurant']:.1f}")
        print("="*60)
        print(f"\n📝 Stats saved to: {self.stats_file}")
        print(f"📋 Recommendations saved to: {self.recommendations_file}")
        print()
