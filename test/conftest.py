"""pytest hooks (currently just used to order tests)"""

import os
import sys

# pylint: disable=unused-argument

sys.path[:] = [os.path.dirname(os.path.realpath(__file__)) + "/.."] + sys.path


def pytest_collection_modifyitems(session, config, items):
    """Modify collected tests (used to set ordering)"""

    def get_item_location(iitem):
        return iitem.cls.__name__, iitem.location

    items.sort(key=get_item_location)
