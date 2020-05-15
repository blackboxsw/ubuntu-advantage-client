from uaclient.entitlements import repo
from uaclient import apt, status, util

try:
    from typing import Any, Callable, Dict, List, Set, Tuple, Union  # noqa

    StaticAffordance = Tuple[str, Callable[[], Any], bool]
except ImportError:
    # typing isn't available on trusty, so ignore its absence
    pass


class FIPSCommonEntitlement(repo.RepoEntitlement):

    repo_pin_priority = 1001
    fips_required_packages = frozenset({"fips-initramfs", "linux-fips"})
    fips_packages = {
        "libssl1.0.0": {"libssl1.0.0-hmac"},
        "openssh-client": {"openssh-client-hmac"},
        "openssh-server": {"openssh-server-hmac"},
        "openssl": set(),
        "strongswan": {"strongswan-hmac"},
    }  # type: Dict[str, Set[str]]
    repo_key_file = "ubuntu-advantage-fips.gpg"  # Same for fips & fips-updates

    @property
    def packages(self) -> "List[str]":
        packages = list(self.fips_required_packages)
        installed_packages = apt.get_installed_packages()
        for pkg_name, extra_pkgs in self.fips_packages.items():
            if pkg_name in installed_packages:
                packages.append(pkg_name)
                packages.extend(extra_pkgs)
        return packages

    def application_status(self) -> "Tuple[status.ApplicationStatus, str]":
        super_status, super_msg = super().application_status()
        if super_status != status.ApplicationStatus.ENABLED:
            return super_status, super_msg
        running_kernel = util.get_platform_info()["kernel"]
        if running_kernel.endswith("-fips"):
            return super_status, super_msg
        return (
            status.ApplicationStatus.ENABLED,
            "Reboot to FIPS kernel required",
        )

    def disable(self, silent: bool = False) -> bool:
        """FIPS cannot be disabled, so simply display a message to the user"""
        if not silent:
            print("Warning: no option to disable {}".format(self.title))
        return False

    def _cleanup(self) -> None:
        """FIPS can't be cleaned up automatically, so don't do anything"""
        pass


class FIPSEntitlement(FIPSCommonEntitlement):

    help_doc_url = "https://ubuntu.com/fips"
    name = "fips"
    title = "FIPS"
    description = "NIST-certified FIPS modules"
    origin = "UbuntuFIPS"

    @property
    def static_affordances(self) -> "Tuple[StaticAffordance, ...]":
        return (
            ("Cannot install FIPS on a container", util.is_container, False),
        )

    @property
    def messaging(
        self
    ) -> "Dict[str, List[Union[str, Tuple[Callable, Dict]]]]":
        return {
            "pre_enable": [
                (
                    util.prompt_for_confirmation,
                    {
                        "msg": status.PROMPT_FIPS_PRE_ENABLE,
                        "assume_yes": self.assume_yes,
                    },
                )
            ],
            "post_enable": [
                status.MESSAGE_ENABLE_REBOOT_REQUIRED_TMPL.format(
                    operation="install"
                )
            ],
            "pre_disable": [
                (
                    util.prompt_for_confirmation,
                    {
                        "assume_yes": self.assume_yes,
                        "msg": status.PROMPT_FIPS_PRE_DISABLE,
                    },
                )
            ],
            "post_disable": [
                status.MESSAGE_ENABLE_REBOOT_REQUIRED_TMPL.format(
                    operation="disable operation"
                )
            ],
        }


class FIPSUpdatesEntitlement(FIPSCommonEntitlement):

    name = "fips-updates"
    title = "FIPS Updates"
    origin = "UbuntuFIPSUpdates"
    description = "Uncertified security updates to FIPS modules"

    @property
    def messaging(
        self
    ) -> "Dict[str, List[Union[str, Tuple[Callable, Dict]]]]":
        return {
            "pre_enable": [
                (
                    util.prompt_for_confirmation,
                    {
                        "msg": status.PROMPT_FIPS_UPDATES_PRE_ENABLE,
                        "assume_yes": self.assume_yes,
                    },
                )
            ],
            "post_enable": [
                status.MESSAGE_ENABLE_REBOOT_REQUIRED_TMPL.format(
                    operation="install"
                )
            ],
            "pre_disable": [
                (
                    util.prompt_for_confirmation,
                    {
                        "assume_yes": self.assume_yes,
                        "msg": status.PROMPT_FIPS_PRE_DISABLE,
                    },
                )
            ],
            "post_disable": [
                status.MESSAGE_ENABLE_REBOOT_REQUIRED_TMPL.format(
                    operation="disable operation"
                )
            ],
        }

    @property
    def static_affordances(self) -> "Tuple[StaticAffordance, ...]":
        return (
            (
                "Cannot install FIPS Updates on a container",
                util.is_container,
                False,
            ),
        )
