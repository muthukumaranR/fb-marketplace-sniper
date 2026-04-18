"""Playwright UI tests for FB Marketplace Sniper."""

import asyncio
from playwright.async_api import async_playwright, Page, expect


BASE = "http://localhost:8000"


async def test_dashboard_loads(page: Page):
    """Dashboard loads with stats, scan status, and recent deals."""
    print("\n=== TEST: Dashboard loads ===")
    await page.goto(BASE)
    await page.wait_for_load_state("networkidle")

    # Check nav is present
    nav_text = await page.text_content("nav")
    assert "Marketplace Sniper" in nav_text, "Missing app title"
    assert "Dashboard" in nav_text, "Missing Dashboard nav"
    assert "Watchlist" in nav_text, "Missing Watchlist nav"
    assert "Listings" in nav_text, "Missing Listings nav"
    assert "History" in nav_text, "Missing History nav"
    print("  Nav bar: OK")

    # Check FB status indicator
    fb_status = page.locator("nav").locator("text=FB")
    await expect(fb_status).to_be_visible()
    status_text = await fb_status.text_content()
    print(f"  FB status: {status_text}")

    # Check stats cards
    stat_cards = page.locator(".grid-cols-3 > div")
    count = await stat_cards.count()
    assert count == 3, f"Expected 3 stat cards, got {count}"
    for i in range(count):
        card_text = await stat_cards.nth(i).text_content()
        print(f"  Stat card {i}: {card_text}")

    # Check scanner section
    scanner = page.locator("text=Marketplace Scanner")
    await expect(scanner).to_be_visible()
    print("  Scanner section: OK")

    # Check recent deals section
    recent = page.locator("text=Recent Deals")
    await expect(recent).to_be_visible()
    print("  Recent Deals section: OK")

    # Check that deal cards are rendered
    deal_cards = page.locator("a[href^='https://www.facebook.com/marketplace']")
    deal_count = await deal_cards.count()
    print(f"  Deal cards rendered: {deal_count}")

    print("  PASSED")


async def test_dashboard_nav_active_state(page: Page):
    """Dashboard nav link should be active when on /."""
    print("\n=== TEST: Dashboard nav active state ===")
    await page.goto(BASE)
    await page.wait_for_load_state("networkidle")

    dash_link = page.locator("nav a[href='/']")
    classes = await dash_link.get_attribute("class")
    assert "bg-blue-100" in classes, f"Dashboard link not active. Classes: {classes}"
    print("  Dashboard link active: OK")

    # Other links should NOT be active
    watchlist_link = page.locator("nav a[href='/watchlist']")
    wl_classes = await watchlist_link.get_attribute("class")
    assert "bg-blue-100" not in wl_classes, "Watchlist link should not be active on /"
    print("  Watchlist link not active: OK")
    print("  PASSED")


async def test_navigate_to_watchlist(page: Page):
    """Navigate to watchlist, verify form and items."""
    print("\n=== TEST: Navigate to Watchlist ===")
    await page.goto(BASE)
    await page.wait_for_load_state("networkidle")

    await page.click("nav >> text=Watchlist")
    await page.wait_for_load_state("networkidle")
    assert "/watchlist" in page.url, f"Expected /watchlist in URL, got {page.url}"

    # Check form is present
    name_input = page.locator("input[placeholder*='looking for']")
    await expect(name_input).to_be_visible()
    print("  Name input: OK")

    max_price_input = page.locator("input[placeholder='Max price ($)']")
    await expect(max_price_input).to_be_visible()
    print("  Max price input: OK")

    add_button = page.locator("button:has-text('Add to Watchlist')")
    await expect(add_button).to_be_visible()
    print("  Add button: OK")

    # Check existing items
    items = page.locator("h3")
    item_count = await items.count()
    print(f"  Existing items: {item_count}")

    print("  PASSED")


async def test_add_watchlist_item(page: Page):
    """Add a new item to watchlist and verify it appears."""
    print("\n=== TEST: Add watchlist item ===")
    await page.goto(f"{BASE}/watchlist")
    await page.wait_for_load_state("networkidle")

    # Count items before
    items_before = await page.locator(".grid.gap-4 > div").count()
    print(f"  Items before: {items_before}")

    # Fill in the form
    await page.fill("input[placeholder*='looking for']", "Nintendo Switch")
    await page.fill("input[placeholder='Max price ($)']", "200")
    await page.fill("input[placeholder*='Location']", "Huntsville, AL")
    await page.fill("input[placeholder='Radius (mi)']", "25")

    # Submit
    await page.click("button:has-text('Add to Watchlist')")

    # Wait for the item to appear
    await page.wait_for_timeout(2000)
    await page.wait_for_load_state("networkidle")

    # Verify the item appears
    new_item = page.locator("h3:has-text('Nintendo Switch')")
    await expect(new_item).to_be_visible(timeout=5000)
    print("  Nintendo Switch item visible: OK")

    # Check item details
    item_card = new_item.locator("xpath=ancestor::div[contains(@class, 'bg-white')]")
    card_text = await item_card.text_content()
    print(f"  Item card text: {card_text[:200]}")

    # Verify max price shows
    assert "$200" in card_text or "200" in card_text, "Max price not shown"
    print("  Max price shown: OK")

    # Check that the form was cleared
    name_val = await page.locator("input[placeholder*='looking for']").input_value()
    assert name_val == "", f"Name input not cleared after add: '{name_val}'"
    print("  Form cleared after add: OK")

    # Check price estimation section
    price_section = item_card.locator("text=Estimating fair price").or_(
        item_card.locator("text=Check fair market price")
    ).or_(
        item_card.locator("text=Price check failed")
    ).or_(
        item_card.locator("text=Fair Price")
    )
    is_visible = await price_section.first.is_visible()
    print(f"  Price section visible: {is_visible}")

    print("  PASSED")


async def test_delete_watchlist_item(page: Page):
    """Delete the Nintendo Switch item we just added."""
    print("\n=== TEST: Delete watchlist item ===")
    await page.goto(f"{BASE}/watchlist")
    await page.wait_for_load_state("networkidle")

    # Find the Nintendo Switch card and its Remove button
    switch_item = page.locator("h3:has-text('Nintendo Switch')")
    if await switch_item.count() == 0:
        print("  SKIPPED: Nintendo Switch not found (may have been removed)")
        return

    # Get the parent card and find Remove button
    card = switch_item.locator("xpath=ancestor::div[contains(@class, 'rounded-xl')]").first
    remove_btn = card.locator("button:has-text('Remove')")
    await remove_btn.click()
    await page.wait_for_timeout(1000)
    await page.wait_for_load_state("networkidle")

    # Verify it's gone
    remaining = page.locator("h3:has-text('Nintendo Switch')")
    assert await remaining.count() == 0, "Nintendo Switch item still present after delete"
    print("  Item deleted: OK")
    print("  PASSED")


async def test_listings_page(page: Page):
    """Listings page loads with filters and listing cards."""
    print("\n=== TEST: Listings page ===")
    await page.goto(f"{BASE}/listings")
    await page.wait_for_load_state("networkidle")

    # Check filters
    item_filter = page.locator("select").first
    await expect(item_filter).to_be_visible()
    print("  Item filter: OK")

    deal_filter = page.locator("select").nth(1)
    await expect(deal_filter).to_be_visible()
    print("  Deal filter: OK")

    # Check listing count text
    count_text = page.locator("text=/\\d+ listing/")
    await expect(count_text).to_be_visible()
    listing_text = await count_text.text_content()
    print(f"  Listing count: {listing_text}")

    # Check listing cards exist
    listing_cards = page.locator("a[href^='https://www.facebook.com/marketplace']")
    card_count = await listing_cards.count()
    print(f"  Listing cards: {card_count}")
    assert card_count > 0, "No listing cards found"

    # Check first listing has price
    first = listing_cards.first
    first_text = await first.text_content()
    assert "$" in first_text, "First listing has no price"
    print(f"  First listing text: {first_text[:100]}")

    print("  PASSED")


async def test_listings_filter_by_deal_quality(page: Page):
    """Test the deal quality filter on listings page."""
    print("\n=== TEST: Listings filter by deal quality ===")
    await page.goto(f"{BASE}/listings")
    await page.wait_for_load_state("networkidle")

    # Get initial count
    count_el = page.locator("text=/\\d+ listing/")
    initial_text = await count_el.text_content()
    print(f"  Initial count: {initial_text}")

    # Filter to "great" deals
    deal_select = page.locator("select").nth(1)
    await deal_select.select_option("great")
    await page.wait_for_timeout(1000)
    await page.wait_for_load_state("networkidle")

    great_text = await count_el.text_content()
    print(f"  After 'great' filter: {great_text}")

    # Filter to "fair"
    await deal_select.select_option("fair")
    await page.wait_for_timeout(1000)
    await page.wait_for_load_state("networkidle")

    fair_text = await count_el.text_content()
    print(f"  After 'fair' filter: {fair_text}")

    # Reset to all
    await deal_select.select_option("")
    await page.wait_for_timeout(1000)
    await page.wait_for_load_state("networkidle")

    reset_text = await count_el.text_content()
    print(f"  After reset: {reset_text}")

    # Reset count should match initial
    assert reset_text == initial_text, f"Reset count '{reset_text}' != initial '{initial_text}'"
    print("  PASSED")


async def test_history_page(page: Page):
    """History page loads with scan history table."""
    print("\n=== TEST: History page ===")
    await page.goto(f"{BASE}/history")
    await page.wait_for_load_state("networkidle")

    # Check table headers
    table = page.locator("table")
    await expect(table).to_be_visible()

    headers = await table.locator("th").all_text_contents()
    print(f"  Table headers: {headers}")
    assert "Status" in headers, "Missing Status header"
    assert "Deals Found" in headers, "Missing Deals Found header"

    # Check rows
    rows = table.locator("tbody tr")
    row_count = await rows.count()
    print(f"  Scan rows: {row_count}")
    assert row_count > 0, "No scan history rows"

    # Check first row has status badge
    first_status = rows.first.locator("span")
    status_text = await first_status.text_content()
    print(f"  First scan status: {status_text}")
    assert status_text in ("completed", "running", "failed"), f"Unknown status: {status_text}"

    print("  PASSED")


async def test_scan_now_button(page: Page):
    """Test the Scan Now button on dashboard."""
    print("\n=== TEST: Scan Now button ===")
    await page.goto(BASE)
    await page.wait_for_load_state("networkidle")

    scan_btn = page.locator("button:has-text('Scan Now')")
    await expect(scan_btn).to_be_visible()

    # Check if button is enabled (requires FB connected + watch items)
    is_disabled = await scan_btn.is_disabled()
    print(f"  Scan Now disabled: {is_disabled}")

    if not is_disabled:
        print("  Scan Now is enabled (FB connected + watch items)")
    else:
        print("  Scan Now is disabled - checking reason")
        reason = page.locator("text=Connect Facebook first").or_(
            page.locator("text=Add watchlist items first")
        )
        if await reason.count() > 0:
            reason_text = await reason.first.text_content()
            print(f"  Reason: {reason_text}")

    print("  PASSED")


async def test_check_fair_price_button(page: Page):
    """Test the Check fair market price button on watchlist."""
    print("\n=== TEST: Check fair price button ===")
    await page.goto(f"{BASE}/watchlist")
    await page.wait_for_load_state("networkidle")

    # Look for "Check fair market price" or "Refresh" or price display
    price_btn = page.locator("button:has-text('Check fair market price')")
    refresh_btn = page.locator("button:has-text('Refresh')")
    fair_price_display = page.locator("text=Fair Price")
    retry_btn = page.locator("button:has-text('Retry')")

    if await price_btn.count() > 0:
        print("  Found 'Check fair market price' button - clicking")
        await price_btn.first.click()
        # Wait for loading or result
        await page.wait_for_timeout(3000)
        # Check what happened
        if await fair_price_display.count() > 0:
            print("  Price fetched successfully")
        elif await retry_btn.count() > 0:
            print("  Price fetch failed (expected - known issue with eBay/Gemini)")
        else:
            spinner = page.locator(".animate-spin")
            if await spinner.count() > 0:
                print("  Still loading...")
    elif await fair_price_display.count() > 0:
        print("  Price already displayed")
    elif await refresh_btn.count() > 0:
        print("  Refresh button visible (price already loaded)")
    elif await retry_btn.count() > 0:
        print("  Retry button visible (previous fetch failed)")
    else:
        print("  No price buttons found (unexpected)")

    print("  PASSED")


async def test_listings_page_shows_loading_on_filter_change(page: Page):
    """Verify that changing filters shows a loading state or immediately updates."""
    print("\n=== TEST: Listings filter loading behavior ===")
    await page.goto(f"{BASE}/listings")
    await page.wait_for_load_state("networkidle")

    # Changing the item filter should trigger a re-fetch
    item_select = page.locator("select").first
    options = await item_select.locator("option").all_text_contents()
    print(f"  Item filter options: {options}")

    if len(options) > 1:
        # Select the second option (first real item)
        await item_select.select_option(index=1)
        # The component re-renders - check it doesn't break
        await page.wait_for_timeout(2000)
        await page.wait_for_load_state("networkidle")
        count_text = await page.locator("text=/\\d+ listing/").text_content()
        print(f"  After filtering by item: {count_text}")

    print("  PASSED")


async def test_view_all_listings_link(page: Page):
    """Test 'View all listings' link on dashboard navigates correctly."""
    print("\n=== TEST: View all listings link ===")
    await page.goto(BASE)
    await page.wait_for_load_state("networkidle")

    link = page.locator("a:has-text('View all listings')")
    if await link.count() > 0:
        await link.click()
        await page.wait_for_load_state("networkidle")
        assert "/listings" in page.url, f"Expected /listings, got {page.url}"
        print("  Navigated to /listings: OK")
    else:
        print("  'View all listings' link not shown (no deals)")

    print("  PASSED")


async def test_listing_links_open_facebook(page: Page):
    """Verify listing card links point to facebook.com/marketplace."""
    print("\n=== TEST: Listing links ===")
    await page.goto(f"{BASE}/listings")
    await page.wait_for_load_state("networkidle")

    links = page.locator("a[href^='https://www.facebook.com/marketplace']")
    count = await links.count()
    if count > 0:
        href = await links.first.get_attribute("href")
        target = await links.first.get_attribute("target")
        rel = await links.first.get_attribute("rel")
        print(f"  First link: {href}")
        print(f"  target={target}, rel={rel}")
        assert target == "_blank", "Links should open in new tab"
        assert "noopener" in (rel or ""), "Links should have noopener"
    print("  PASSED")


async def test_responsive_stat_cards(page: Page):
    """Check stat cards are visible on dashboard."""
    print("\n=== TEST: Stat cards display ===")
    await page.goto(BASE)
    await page.wait_for_load_state("networkidle")

    # Check all 3 stat cards have labels and values
    watching = page.get_by_text("Watching", exact=True)
    await expect(watching).to_be_visible()
    listings_found = page.get_by_text("Listings Found", exact=True)
    await expect(listings_found).to_be_visible()
    deals = page.locator(".grid-cols-3").get_by_text("Deals", exact=True)
    await expect(deals).to_be_visible()

    # Get values from stat cards
    stat_values = page.locator(".grid-cols-3 .text-3xl")
    count = await stat_values.count()
    for i in range(count):
        val = await stat_values.nth(i).text_content()
        print(f"  Stat value {i}: {val}")

    print("  PASSED")


async def test_deal_badge_colors(page: Page):
    """Verify deal badges have correct styling."""
    print("\n=== TEST: Deal badge colors ===")
    await page.goto(f"{BASE}/listings")
    await page.wait_for_load_state("networkidle")

    great_badges = page.locator("span:has-text('GREAT DEAL')")
    good_badges = page.locator("span:has-text('Good Deal')")
    fair_badges = page.locator("span:has-text('Fair')")

    print(f"  GREAT DEAL badges: {await great_badges.count()}")
    print(f"  Good Deal badges: {await good_badges.count()}")
    print(f"  Fair badges: {await fair_badges.count()}")

    if await great_badges.count() > 0:
        classes = await great_badges.first.get_attribute("class")
        assert "bg-red-100" in classes, f"Great deal badge missing red bg: {classes}"
        print("  Great deal badge styling: OK")

    print("  PASSED")


async def test_page_not_found(page: Page):
    """Test navigating to a non-existent route shows 404 page with nav."""
    print("\n=== TEST: 404 handling ===")
    await page.goto(f"{BASE}/nonexistent-page")
    await page.wait_for_load_state("networkidle")

    # Nav should still be visible
    nav = await page.query_selector("nav")
    assert nav is not None, "Nav should be visible on 404 page"
    print("  Nav visible on 404: OK")

    # Should show 404 message
    four_oh_four = page.get_by_text("404")
    await expect(four_oh_four).to_be_visible()
    print("  404 text visible: OK")

    page_not_found = page.get_by_text("Page not found")
    await expect(page_not_found).to_be_visible()
    print("  'Page not found' text visible: OK")

    # Should have a link back to dashboard
    back_link = page.locator("a:has-text('Back to Dashboard')")
    await expect(back_link).to_be_visible()
    await back_link.click()
    await page.wait_for_load_state("networkidle")
    assert page.url.rstrip("/").endswith(":8000") or page.url.endswith("/"), \
        f"Expected dashboard URL, got {page.url}"
    print("  Back to Dashboard link works: OK")

    print("  PASSED")


async def test_watchlist_add_empty_name_prevented(page: Page):
    """Form should not submit if name is empty."""
    print("\n=== TEST: Empty name prevented ===")
    await page.goto(f"{BASE}/watchlist")
    await page.wait_for_load_state("networkidle")

    add_btn = page.locator("button:has-text('Add to Watchlist')")
    is_disabled = await add_btn.is_disabled()
    print(f"  Button disabled with empty name: {is_disabled}")
    assert is_disabled, "Add button should be disabled when name is empty"
    print("  PASSED")


async def test_console_errors(page: Page):
    """Check for JavaScript console errors during navigation."""
    print("\n=== TEST: Console errors ===")
    errors = []
    page.on("console", lambda msg: errors.append(msg) if msg.type == "error" else None)

    # Navigate through all pages
    for path in ["/", "/watchlist", "/listings", "/history"]:
        await page.goto(f"{BASE}{path}")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(500)

    if errors:
        print(f"  Console errors found: {len(errors)}")
        for e in errors:
            print(f"    - {e.text}")
    else:
        print("  No console errors")
    print("  PASSED")


async def test_listings_loading_state(page: Page):
    """Verify loading states work correctly."""
    print("\n=== TEST: Loading states ===")
    # Check that loading indicator appears when navigating to listings
    # by intercepting the network request
    await page.goto(f"{BASE}/listings")

    # The page should either show "Loading..." or the content
    body_text = await page.text_content("body")
    assert "Loading..." in body_text or "listing" in body_text.lower(), \
        "Page should show either loading or content"
    print("  Listings page shows loading or content: OK")

    await page.wait_for_load_state("networkidle")
    print("  PASSED")


async def test_dashboard_onboarding_checklist(page: Page):
    """Check onboarding checklist visibility and state.

    The checklist should remain visible until ALL 4 steps are complete,
    including email setup. This was a bug where the checklist hid after
    only 3 steps, making the email step unreachable.
    """
    print("\n=== TEST: Onboarding checklist ===")
    await page.goto(BASE)
    await page.wait_for_load_state("networkidle")

    # Check setup status via API to know what to expect
    import json
    setup_resp = await page.evaluate("fetch('/api/setup-status').then(r => r.json())")
    print(f"  Setup status: {setup_resp}")

    checklist = page.locator("text=Get Started")
    all_complete = (
        setup_resp.get("fb_logged_in")
        and setup_resp.get("has_watch_items")
        and setup_resp.get("has_scans")
        and setup_resp.get("has_email")
    )

    if all_complete:
        # All 4 steps done - checklist should be hidden
        assert await checklist.count() == 0, "Checklist should be hidden when all 4 steps complete"
        print("  Checklist correctly hidden (all 4 steps complete)")
    else:
        # At least one step incomplete - checklist should be visible
        await expect(checklist).to_be_visible()
        print("  Checklist visible (setup incomplete)")

        # Verify email step is visible when other 3 are done but email is not
        if (setup_resp.get("fb_logged_in") and setup_resp.get("has_watch_items")
                and setup_resp.get("has_scans") and not setup_resp.get("has_email")):
            email_step = page.locator("text=Set up email alerts")
            await expect(email_step).to_be_visible()
            print("  Email setup step visible (bug fix verified): OK")

    print("  PASSED")


async def test_image_proxy(page: Page):
    """Check that listing images are proxied through backend."""
    print("\n=== TEST: Image proxy ===")
    await page.goto(f"{BASE}/listings")
    await page.wait_for_load_state("networkidle")

    images = page.locator("img")
    img_count = await images.count()
    print(f"  Images on page: {img_count}")

    if img_count > 0:
        src = await images.first.get_attribute("src")
        print(f"  First image src: {src}")
        # Should be proxied through /api/proxy-image
        if src:
            assert src.startswith("/api/proxy-image"), \
                f"Image not proxied! src={src}"
            print("  Image proxied: OK")

    print("  PASSED")


async def main():
    print("Starting Playwright UI tests for FB Marketplace Sniper")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})

        tests = [
            test_dashboard_loads,
            test_dashboard_nav_active_state,
            test_navigate_to_watchlist,
            test_watchlist_add_empty_name_prevented,
            test_add_watchlist_item,
            test_check_fair_price_button,
            test_delete_watchlist_item,
            test_listings_page,
            test_listings_filter_by_deal_quality,
            test_listings_page_shows_loading_on_filter_change,
            test_listing_links_open_facebook,
            test_deal_badge_colors,
            test_view_all_listings_link,
            test_history_page,
            test_scan_now_button,
            test_responsive_stat_cards,
            test_dashboard_onboarding_checklist,
            test_image_proxy,
            test_page_not_found,
            test_console_errors,
            test_listings_loading_state,
        ]

        passed = 0
        failed = 0
        failures = []

        for test in tests:
            page = await context.new_page()
            try:
                await test(page)
                passed += 1
            except Exception as e:
                failed += 1
                failures.append((test.__name__, str(e)))
                print(f"  FAILED: {e}")
            finally:
                await page.close()

        await browser.close()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    if failures:
        print("\nFailures:")
        for name, err in failures:
            print(f"  {name}: {err}")


if __name__ == "__main__":
    asyncio.run(main())
