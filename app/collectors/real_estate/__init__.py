"""``playwright_jsonld`` real estate listing collectors.

All three sites (KV.ee, Kinnisvara24, City24) use the same implementation
strategy, so their entire collection logic lives once in
``base_listing_collector.BaseListingCollector``; each site's module is a
thin subclass supplying only its identity and configuration.
"""
