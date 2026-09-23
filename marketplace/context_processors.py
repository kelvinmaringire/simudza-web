def cart_context(request):
    """Cart UI is Alpine + localStorage; only expose sync flags for the client."""
    return {
        "cart_can_sync": request.user.is_authenticated,
    }
