from uaclient.entitlements.base import UAEntitlement  # noqa: F401
from uaclient.entitlements.cc import CommonCriteriaEntitlement
from uaclient.entitlements.cis import CISEntitlement
from uaclient.entitlements.esm import ESMEntitlement
from uaclient.entitlements import fips
from uaclient.entitlements.livepatch import LivepatchEntitlement

try:
    from typing import cast, Dict, List, Type  # noqa: F401
except ImportError:
    # typing isn't available on trusty, so ignore its absence
    def cast(_, x):
        return x

ENTITLEMENT_CLASSES = [
    CommonCriteriaEntitlement, CISEntitlement, ESMEntitlement,
    fips.FIPSEntitlement, fips.FIPSUpdatesEntitlement,
    LivepatchEntitlement]  # type: List[Type[UAEntitlement]]

ENTITLEMENT_CLASS_BY_NAME = dict(
    (cast(str, cls.name), cls)
    for cls in ENTITLEMENT_CLASSES)  # type: Dict[str, Type[UAEntitlement]]
