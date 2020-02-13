""" Utility Methods for extension package. """


def exclude_app_urls(urls, app_name):
    """ Exclude the given app's urls

        Args:
            urls (list): List of url patterns
            app_name: Name of app whose urls are needed to be removed

        Returns: Updated urls
        """
    for i, item in enumerate(urls):
        if hasattr(item, 'app_name') and item.app_name == app_name:
            urls.pop(i)
            return urls
    return urls
