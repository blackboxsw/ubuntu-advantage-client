import contextlib
import mock
import os.path

import pytest

from uaclient import apt
from uaclient.entitlements.esm import ESMAppsEntitlement, ESMInfraEntitlement
from uaclient import exceptions
from uaclient import util

M_PATH = "uaclient.entitlements.esm.ESMInfraEntitlement."
M_REPOPATH = "uaclient.entitlements.repo."
M_GETPLATFORM = M_REPOPATH + "util.get_platform_info"


@pytest.fixture(params=[ESMAppsEntitlement, ESMInfraEntitlement])
def entitlement(request, entitlement_factory):
    return entitlement_factory(request.param, suites=["trusty"])


class TestESMInfraEntitlementEnable:
    def test_enable_configures_apt_sources_and_auth_files(self, entitlement):
        """When entitled, configure apt repo auth token, pinning and url."""
        patched_packages = ["a", "b"]
        original_exists = os.path.exists

        def fake_exists(path):
            prefs_path = "/etc/apt/preferences.d/ubuntu-{}-trusty".format(
                entitlement.name
            )
            if path == prefs_path:
                return True
            if path in (apt.APT_METHOD_HTTPS_FILE, apt.CA_CERTIFICATES_FILE):
                return True
            return original_exists(path)

        with contextlib.ExitStack() as stack:
            m_add_apt = stack.enter_context(
                mock.patch("uaclient.apt.add_auth_apt_repo")
            )
            m_add_pinning = stack.enter_context(
                mock.patch("uaclient.apt.add_ppa_pinning")
            )
            m_subp = stack.enter_context(
                mock.patch("uaclient.util.subp", return_value=("", ""))
            )
            m_can_enable = stack.enter_context(
                mock.patch.object(entitlement, "can_enable")
            )
            stack.enter_context(
                mock.patch(M_GETPLATFORM, return_value={"series": "trusty"})
            )
            stack.enter_context(
                mock.patch(
                    M_REPOPATH + "os.path.exists", side_effect=fake_exists
                )
            )
            # Note that this patch uses a PropertyMock and happens on the
            # entitlement's type because packages is a property
            m_packages = mock.PropertyMock(return_value=patched_packages)
            stack.enter_context(
                mock.patch.object(type(entitlement), "packages", m_packages)
            )

            m_can_enable.return_value = True

            assert True is entitlement.enable()

        add_apt_calls = [
            mock.call(
                "/etc/apt/sources.list.d/ubuntu-{}-trusty.list".format(
                    entitlement.name
                ),
                "http://{}".format(entitlement.name.upper()),
                "%s-token" % entitlement.name,
                ["trusty"],
                entitlement.repo_key_file,
            )
        ]
        install_cmd = mock.call(
            ["apt-get", "install", "--assume-yes"] + patched_packages,
            capture=True,
            retry_sleeps=apt.APT_RETRIES,
        )

        subp_calls = [
            mock.call(
                ["apt-get", "update"],
                capture=True,
                retry_sleeps=apt.APT_RETRIES,
            ),
            install_cmd,
        ]

        assert [mock.call(silent=mock.ANY)] == m_can_enable.call_args_list
        assert add_apt_calls == m_add_apt.call_args_list
        assert 0 == m_add_pinning.call_count
        assert subp_calls == m_subp.call_args_list

    def test_enable_cleans_up_apt_sources_and_auth_files_on_error(
        self, entitlement, caplog_text
    ):
        """When setup_apt_config fails, cleanup any apt artifacts."""
        original_exists = os.path.exists

        def fake_exists(path):
            prefs_path = "/etc/apt/preferences.d/ubuntu-{}-trusty".format(
                entitlement.name
            )
            if path == prefs_path:
                return True
            if path in (apt.APT_METHOD_HTTPS_FILE, apt.CA_CERTIFICATES_FILE):
                return True
            return original_exists(path)

        def fake_subp(cmd, capture=None, retry_sleeps=None):
            if cmd == ["apt-get", "update"]:
                raise util.ProcessExecutionError(
                    "Failure", stderr="Could not get lock /var/lib/dpkg/lock"
                )
            return "", ""

        with contextlib.ExitStack() as stack:
            m_add_apt = stack.enter_context(
                mock.patch("uaclient.apt.add_auth_apt_repo")
            )
            m_add_pinning = stack.enter_context(
                mock.patch("uaclient.apt.add_ppa_pinning")
            )
            m_subp = stack.enter_context(
                mock.patch("uaclient.util.subp", side_effect=fake_subp)
            )
            m_can_enable = stack.enter_context(
                mock.patch.object(entitlement, "can_enable")
            )
            m_remove_apt_config = stack.enter_context(
                mock.patch.object(entitlement, "remove_apt_config")
            )
            stack.enter_context(
                mock.patch(M_GETPLATFORM, return_value={"series": "trusty"})
            )
            stack.enter_context(
                mock.patch(
                    M_REPOPATH + "os.path.exists", side_effect=fake_exists
                )
            )

            m_can_enable.return_value = True

            with pytest.raises(exceptions.UserFacingError) as excinfo:
                entitlement.enable()

        add_apt_calls = [
            mock.call(
                "/etc/apt/sources.list.d/ubuntu-{}-trusty.list".format(
                    entitlement.name
                ),
                "http://{}".format(entitlement.name.upper()),
                "%s-token" % entitlement.name,
                ["trusty"],
                entitlement.repo_key_file,
            )
        ]
        subp_calls = [
            mock.call(
                ["apt-get", "update"],
                capture=True,
                retry_sleeps=apt.APT_RETRIES,
            )
        ]

        error_msg = "APT update failed. Another process is running APT."
        assert error_msg == excinfo.value.msg
        assert [mock.call(silent=mock.ANY)] == m_can_enable.call_args_list
        assert add_apt_calls == m_add_apt.call_args_list
        assert 0 == m_add_pinning.call_count
        assert subp_calls == m_subp.call_args_list
        assert [mock.call()] == m_remove_apt_config.call_args_list


class TestESMInfraEntitlementDisable:
    @pytest.mark.parametrize("silent", [False, True])
    @mock.patch("uaclient.util.get_platform_info")
    @mock.patch(M_PATH + "can_disable", return_value=False)
    def test_disable_returns_false_on_can_disable_false_and_does_nothing(
        self, m_can_disable, m_platform_info, silent
    ):
        """When can_disable is false disable returns false and noops."""
        entitlement = ESMInfraEntitlement({})

        with mock.patch("uaclient.apt.remove_auth_apt_repo") as m_remove_apt:
            assert False is entitlement.disable(silent)
        assert [mock.call(silent)] == m_can_disable.call_args_list
        assert 0 == m_remove_apt.call_count

    @mock.patch(M_REPOPATH + "apt.remove_apt_list_files")
    @mock.patch(M_REPOPATH + "apt.remove_auth_apt_repo")
    @mock.patch(
        "uaclient.util.get_platform_info", return_value={"series": "trusty"}
    )
    def test_disable_removes_apt_config(
        self,
        m_platform_info,
        m_remove_auth_apt_repo,
        m_remove_apt_list_files,
        entitlement,
        tmpdir,
    ):
        """When can_disable, disable removes apt configuration"""

        with mock.patch.object(
            entitlement, "can_disable", return_value=True
        ) as m_can_disable:
            with mock.patch("uaclient.entitlements.repo.apt.run_apt_command"):
                with mock.patch("uaclient.util.subp"):
                    assert entitlement.disable(True)

        assert [mock.call(True)] == m_can_disable.call_args_list

        expected_key_name = "ubuntu-advantage-{}.gpg".format(
            entitlement.name
            if isinstance(entitlement, ESMAppsEntitlement)
            else entitlement.name + "-trusty"
        )
        expected_rm_repo_calls = [
            mock.call(
                "/etc/apt/sources.list.d/ubuntu-{}-trusty.list".format(
                    entitlement.name
                ),
                "http://{}".format(entitlement.name.upper()),
                expected_key_name,
            )
        ]
        expected_rm_list_files_calls = [
            mock.call("http://{}".format(entitlement.name.upper()), "trusty")
        ]
        assert expected_rm_repo_calls == m_remove_auth_apt_repo.call_args_list
        assert (
            expected_rm_list_files_calls
            == m_remove_apt_list_files.call_args_list
        )
