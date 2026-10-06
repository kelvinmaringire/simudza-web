def cart_context(request):
    """Cart UI is Alpine + localStorage; sync is available for guests and members."""
    return {
        "cart_can_sync": True,
    }
