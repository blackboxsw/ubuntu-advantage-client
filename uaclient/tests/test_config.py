import json
import os

import pytest

from uaclient.config import PRIVATE_SUBDIR, UAConfig


KNOWN_DATA_PATHS = (('bound-macaroon', 'bound-macaroon'),
                    ('accounts', 'accounts.json'))


class TestAccounts(object):

    def test_accounts_returns_empty_list_when_no_cached_account_value(
            self, tmpdir):
        """Config.accounts property returns an empty list when no cache."""
        cfg = UAConfig({'data_dir': tmpdir.strpath})

        assert [] == cfg.accounts

    def test_accounts_extracts_accounts_key_from_account_read_cache(
            self, tmpdir):
        """Config.accounts property extracts the accounts key from cache."""
        cfg = UAConfig({'data_dir': tmpdir.strpath})
        cfg.write_cache('accounts', {'accounts': ['acct1', 'acct2']})

        assert ['acct1', 'acct2'] == cfg.accounts

    def test_accounts_extracts_accounts_key_from_machine_token_cache(
            self, tmpdir):
        """Use machine_token cached accountInfo when no accounts cache."""
        cfg = UAConfig({'data_dir': tmpdir.strpath})
        accountInfo = {'id': '1', 'name': 'accountname'}

        cfg.write_cache('machine-token',
                        {'machineTokenInfo': {'accountInfo': accountInfo}})

        assert [accountInfo] == cfg.accounts

    def test_accounts_logs_warning_when_non_dictionary_cache_content(
            self, caplog_text, tmpdir):
        """Config.accounts warns and returns empty list on non-dict cache."""
        cfg = UAConfig({'data_dir': tmpdir.strpath})
        cfg.write_cache('accounts', 'non-dict-value')

        assert [] == cfg.accounts
        expected_warning = (
            "WARNING  Unexpected type <class 'str'> in cache %s" % (
                tmpdir.join(PRIVATE_SUBDIR, 'accounts.json')))
        assert expected_warning in caplog_text()

    def test_accounts_logs_warning_when_missing_accounts_key_in_cache(
            self, caplog_text, tmpdir):
        """Config.accounts warns when missing 'accounts' key in cache"""
        cfg = UAConfig({'data_dir': tmpdir.strpath})
        cfg.write_cache('accounts', {'non-accounts': 'somethingelse'})

        assert [] == cfg.accounts
        expected_warning = (
            "WARNING  Missing 'accounts' key in cache %s" %
            tmpdir.join(PRIVATE_SUBDIR, 'accounts.json'))
        assert expected_warning in caplog_text()

    def test_accounts_logs_warning_when_non_list_accounts_cache_content(
            self, caplog_text, tmpdir):
        """Config.accounts warns on non-list accounts key."""
        cfg = UAConfig({'data_dir': tmpdir.strpath})
        cfg.write_cache('accounts', {'accounts': 'non-list-value'})

        assert [] == cfg.accounts
        expected_warning = (
            "WARNING  Unexpected 'accounts' type <class 'str'> in cache %s" % (
                tmpdir.join(PRIVATE_SUBDIR, 'accounts.json')))
        assert expected_warning in caplog_text()


class TestDataPath(object):

    def test_data_path_returns_data_dir_path_without_key(self):
        """The data_path method returns the data_dir when key is absent."""
        cfg = UAConfig({'data_dir': '/my/dir'})
        assert '/my/dir/%s' % PRIVATE_SUBDIR == cfg.data_path()

    @pytest.mark.parametrize('key,path_basename', KNOWN_DATA_PATHS)
    def test_data_path_returns_file_path_with_defined_data_paths(
            self, key, path_basename):
        """When key is defined in Config.data_paths return data_path value."""
        cfg = UAConfig({'data_dir': '/my/dir'})
        private_path = '/my/dir/%s/%s' % (PRIVATE_SUBDIR, path_basename)
        assert private_path == cfg.data_path(key=key)

    @pytest.mark.parametrize('key,path_basename', (
        ('notHere', 'notHere'), ('anything', 'anything')))
    def test_data_path_returns_file_path_with_undefined_data_paths(
            self, key, path_basename):
        """When key is not in Config.data_paths the key is used to data_dir"""
        cfg = UAConfig({'data_dir': '/my/d'})
        assert '/my/d/%s/%s' % (PRIVATE_SUBDIR, key) == cfg.data_path(key=key)

    @pytest.mark.parametrize('key,path_basename', (
        ('notHere', 'notHere'), ('anything', 'anything')))
    def test_data_path_returns_file_path_with_public_data_paths(
            self, key, path_basename):
        """When private is False Config.data_paths return a public path."""
        cfg = UAConfig({'data_dir': '/my/d'})
        assert '/my/d/%s' % key == cfg.data_path(key=key, private=False)


class TestWriteCache(object):

    @pytest.mark.parametrize('key,content', (
        ('unknownkey', 'content1'), ('another-one', 'content2')))
    def test_write_cache_write_key_name_in_data_dir_when_data_path_absent(
            self, tmpdir, key, content):
        """When key is not in data_paths, write content to data_dir/key."""
        cfg = UAConfig({'data_dir': tmpdir.strpath})
        expected_path = tmpdir.join(PRIVATE_SUBDIR, key)

        assert not expected_path.check(), (
            'Found unexpected file %s' % expected_path)
        assert None is cfg.write_cache(key, content)
        assert expected_path.check(), (
            'Missing expected file %s' % expected_path)
        assert content == cfg.read_cache(key)

    def test_write_cache_creates_dir_when_data_dir_does_not_exist(
            self, tmpdir):
        """When data_dir doesn't exist, create it."""
        tmp_subdir = tmpdir.join('does/not/exist')
        cfg = UAConfig({'data_dir': tmp_subdir.strpath})

        assert False is os.path.isdir(tmp_subdir.strpath), (
            'Found unexpected directory %s' % tmp_subdir)
        assert None is cfg.write_cache('somekey', 'someval')
        assert True is os.path.isdir(tmp_subdir.strpath), (
            'Missing expected directory %s' % tmp_subdir)
        assert 'someval' == cfg.read_cache('somekey')

    @pytest.mark.parametrize('key,value', (
        ('dictkey', {'1': 'v1'}), ('listkey', [1, 2, 3])))
    def test_write_cache_writes_json_string_when_content_not_a_string(
            self, tmpdir, key, value):
        """When content is not a string, write a json string."""
        cfg = UAConfig({'data_dir': tmpdir.strpath})

        expected_json_content = json.dumps(value)
        assert None is cfg.write_cache(key, value)
        with open(tmpdir.join(PRIVATE_SUBDIR, key).strpath, 'r') as stream:
            assert expected_json_content == stream.read()
        assert value == cfg.read_cache(key)

    def test_write_cache_writes_non_private_dir_when_private_is_false(
            self, tmpdir):
        """When content is not a string, write a json string."""
        cfg = UAConfig({'data_dir': tmpdir.strpath})

        assert None is cfg.write_cache('key', 'value', private=False)
        with open(tmpdir.join('key').strpath, 'r') as stream:
            assert 'value' == stream.read()
        assert 'value' == cfg.read_cache('key')


class TestReadCache(object):

    @pytest.mark.parametrize('key,path_basename', KNOWN_DATA_PATHS)
    def test_read_cache_returns_none_when_data_path_absent(
            self, tmpdir, key, path_basename):
        """Return None when the specified key data_path is not cached."""
        cfg = UAConfig({'data_dir': tmpdir.strpath})
        assert None is cfg.read_cache(key)
        assert not tmpdir.join(path_basename).check()

    @pytest.mark.parametrize('key,path_basename', KNOWN_DATA_PATHS)
    def test_read_cache_returns_content_when_data_path_present(
            self, tmpdir, key, path_basename):
        cfg = UAConfig({'data_dir': tmpdir.strpath})
        os.makedirs(tmpdir.join(PRIVATE_SUBDIR).strpath)
        data_path = tmpdir.join(PRIVATE_SUBDIR, path_basename)
        with open(data_path.strpath, 'w') as f:
            f.write('content%s' % key)

        assert 'content%s' % key == cfg.read_cache(key)

    @pytest.mark.parametrize('key,path_basename', KNOWN_DATA_PATHS)
    def test_read_cache_returns_stuctured_content_when_json_data_path_present(
            self, tmpdir, key, path_basename):
        cfg = UAConfig({'data_dir': tmpdir.strpath})
        os.makedirs(tmpdir.join(PRIVATE_SUBDIR).strpath)
        data_path = tmpdir.join(PRIVATE_SUBDIR, path_basename)
        expected = {key: 'content%s' % key}
        with open(data_path.strpath, 'w') as f:
            f.write(json.dumps(expected))

        assert expected == cfg.read_cache(key)


class TestDeleteCache(object):

    @pytest.mark.parametrize(
        'property_name,data_path_name,expected_null_value', (
            ('machine_token', 'machine-token', None),
            ('contracts', 'account-contracts', [])))
    def test_delete_cache_properly_clears_all_caches_simple(
            self, tmpdir, property_name, data_path_name, expected_null_value):
        """Ensure that delete_cache clears the cache for simple attributes

        (Simple in this context means those that are simply read from the
        filesystem and returned.)
        """
        property_value = 'our-value'
        cfg = UAConfig({'data_dir': tmpdir.strpath})

        data_path = cfg.data_path(data_path_name)
        os.makedirs(os.path.dirname(data_path))
        with open(data_path, 'w') as f:
            f.write(property_value)

        before_prop_value = getattr(cfg, property_name)
        assert before_prop_value == property_value

        cfg.delete_cache()

        after_prop_value = getattr(cfg, property_name)
        assert expected_null_value == after_prop_value

    def test_delete_cache_unsets_entitlements(self, tmpdir):
        """The delete_cache unsets any cached entitlements content."""
        cfg = UAConfig({'data_dir': tmpdir.strpath})
        token = {
            'machineTokenInfo': {'contractInfo': {'resourceEntitlements': [{
                'type': 'entitlement1', 'entitled': True}]}}}
        cfg.write_cache('machine-token', token)
        previous_entitlements = {
            'entitlement1': {'entitlement':
                                {'type': 'entitlement1', 'entitled': True}}}
        assert previous_entitlements == cfg.entitlements
        cfg.delete_cache()
        assert {} == cfg.entitlements

    def test_delete_cache_removes_any_cached_data_path_files(self, tmpdir):
        """Any cached files defined in cfg.data_paths will be removed."""
        cfg = UAConfig({'data_dir': tmpdir.strpath})
        # Create half of the cached files, but not all
        odd_keys = list(cfg.data_paths.keys())[::2]
        for odd_key in odd_keys:
            cfg.write_cache(odd_key, odd_key)

        private_cachedir = tmpdir.join(PRIVATE_SUBDIR).strpath
        assert len(odd_keys) == len(os.listdir(private_cachedir))
        cfg.delete_cache()
        dirty_files = os.listdir(private_cachedir)
        assert 0 == len(dirty_files), '%d files not deleted' % len(dirty_files)

    def test_delete_cache_ignores_files_not_defined_in_data_paths(
            self, tmpdir):
        """Any files in data_dir undefined in cfg.data_paths will remain."""
        cfg = UAConfig({'data_dir': tmpdir.strpath})
        t_file = tmpdir.join(PRIVATE_SUBDIR, 'otherfile')
        os.makedirs(os.path.dirname(t_file.strpath))
        with open(t_file.strpath, 'w') as f:
            f.write('content')
        assert [os.path.basename(t_file.strpath)] == os.listdir(
            tmpdir.join(PRIVATE_SUBDIR).strpath)
        cfg.delete_cache()
        assert [os.path.basename(t_file.strpath)] == os.listdir(
            tmpdir.join(PRIVATE_SUBDIR).strpath)
