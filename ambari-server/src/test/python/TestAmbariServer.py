'''
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''
from stacks.utils.RMFTestCase import *

import sys
import os
import datetime
import errno
import json
from mock.mock import patch, MagicMock, create_autospec, call
import operator
from optparse import OptionParser
import platform
import re
import shutil
import signal
import stat
import StringIO
import tempfile
from unittest import TestCase

from only_for_platform import get_platform, not_for_platform, only_for_platform, PLATFORM_LINUX, PLATFORM_WINDOWS

if get_platform() != PLATFORM_WINDOWS:
  os_distro_value = ('Suse','11','Final')
  from pwd import getpwnam
else:
  #No Windows tests for now, but start getting prepared
  os_distro_value = ('win2012serverr2','6.3','WindowsServer')

# We have to use this import HACK because the filename contains a dash
with patch("platform.linux_distribution", return_value = os_distro_value):
  with patch("os.symlink"):
    with patch("__builtin__.open"):
      with patch("glob.glob", return_value = ['/etc/init.d/postgresql-9.3']):
        _ambari_server_ = __import__('ambari-server')

        from ambari_commons.firewall import Firewall
        from ambari_commons.os_check import OSCheck, OSConst
        from ambari_commons.exceptions import FatalException, NonFatalException
        from ambari_commons.logging_utils import get_verbose, set_verbose, get_silent, set_silent, get_debug_mode, \
          print_info_msg, print_warning_msg, print_error_msg
        from ambari_commons.os_utils import run_os_command, search_file, set_file_permissions, remove_file, copy_file, \
          is_valid_filepath
        from ambari_server.dbConfiguration import DBMSConfigFactory, check_jdbc_drivers
        from ambari_server.dbConfiguration_linux import PGConfig, LinuxDBMSConfig, OracleConfig
        from ambari_server.properties import Properties
        from ambari_server.resourceFilesKeeper import ResourceFilesKeeper, KeeperException
        from ambari_server.serverConfiguration import configDefaults, \
          check_database_name_property, OS_FAMILY_PROPERTY, \
          find_properties_file, get_ambari_classpath, get_ambari_jars, get_ambari_properties, get_JAVA_HOME, get_share_jars, \
          parse_properties_file, read_ambari_user, update_ambari_properties, update_properties_2, write_property, find_jdk, \
          AMBARI_CONF_VAR, AMBARI_SERVER_LIB, JDBC_DATABASE_PROPERTY, JDBC_RCA_PASSWORD_FILE_PROPERTY, \
          PERSISTENCE_TYPE_PROPERTY, JDBC_URL_PROPERTY, get_conf_dir, JDBC_USER_NAME_PROPERTY, JDBC_PASSWORD_PROPERTY, \
          JDBC_DATABASE_NAME_PROPERTY, OS_TYPE_PROPERTY, validate_jdk, JDBC_POSTGRES_SCHEMA_PROPERTY, \
          RESOURCES_DIR_PROPERTY, JDBC_RCA_PASSWORD_ALIAS, JDBC_RCA_SCHEMA_PROPERTY, IS_LDAP_CONFIGURED, \
          SSL_API, SSL_API_PORT, CLIENT_API_PORT_PROPERTY,\
          LDAP_MGR_PASSWORD_PROPERTY, LDAP_MGR_PASSWORD_ALIAS, JDBC_PASSWORD_FILENAME, NR_USER_PROPERTY, SECURITY_KEY_IS_PERSISTED, \
          SSL_TRUSTSTORE_PASSWORD_PROPERTY, SECURITY_IS_ENCRYPTION_ENABLED, SSL_TRUSTSTORE_PASSWORD_ALIAS, \
          SECURITY_MASTER_KEY_LOCATION, SECURITY_KEYS_DIR, LDAP_PRIMARY_URL_PROPERTY, store_password_file, \
          get_pass_file_path, GET_FQDN_SERVICE_URL, JDBC_USE_INTEGRATED_AUTH_PROPERTY, SECURITY_KEY_ENV_VAR_NAME, \
          JAVA_HOME_PROPERTY
        from ambari_server.serverUtils import is_server_runing, refresh_stack_hash
        from ambari_server.serverSetup import check_selinux, check_ambari_user, proceedJDBCProperties, SE_STATUS_DISABLED, SE_MODE_ENFORCING, configure_os_settings, \
          download_and_install_jdk, prompt_db_properties, setup, \
          AmbariUserChecks, AmbariUserChecksLinux, AmbariUserChecksWindows, JDKSetup, reset, setup_jce_policy, expand_jce_zip_file
        from ambari_server.serverUpgrade import upgrade, upgrade_local_repo, change_objects_owner, upgrade_stack, \
          run_stack_upgrade, run_metainfo_upgrade, run_schema_upgrade, move_user_custom_actions
        from ambari_server.setupHttps import is_valid_https_port, setup_https, import_cert_and_key_action, get_fqdn, \
          generate_random_string, get_cert_info, COMMON_NAME_ATTR, is_valid_cert_exp, NOT_AFTER_ATTR, NOT_BEFORE_ATTR, \
          SSL_DATE_FORMAT, import_cert_and_key, is_valid_cert_host, setup_component_https, \
          SRVR_ONE_WAY_SSL_PORT_PROPERTY, SRVR_TWO_WAY_SSL_PORT_PROPERTY, GANGLIA_HTTPS
        from ambari_server.setupSecurity import adjust_directory_permissions, get_alias_string, get_ldap_event_spec_names, sync_ldap, LdapSyncOptions, \
          configure_ldap_password, setup_ldap, REGEX_HOSTNAME_PORT, REGEX_TRUE_FALSE, REGEX_ANYTHING, setup_master_key, \
          setup_ambari_krb5_jaas
        from ambari_server.userInput import get_YN_input, get_choice_string_input, get_validated_string_input, \
          read_password
        from ambari_server_main import get_ulimit_open_files, ULIMIT_OPEN_FILES_KEY, ULIMIT_OPEN_FILES_DEFAULT

CURR_AMBARI_VERSION = "2.0.0"

@patch("ambari_server.dbConfiguration_linux.get_postgre_hba_dir", new = MagicMock(return_value = "/var/lib/pgsql/data"))
@patch("ambari_server.dbConfiguration_linux.get_postgre_running_status", new = MagicMock(return_value = "running"))
class TestAmbariServer(TestCase):
  def setUp(self):
    out = StringIO.StringIO()
    sys.stdout = out


  def tearDown(self):
    sys.stdout = sys.__stdout__


  @not_for_platform(PLATFORM_WINDOWS)
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  def test_configure_pg_hba_ambaridb_users(self, run_os_command_method):
    # Prepare mocks
    run_os_command_method.return_value = (0, "", "")
    database_username = "ffdf"
    tf1 = tempfile.NamedTemporaryFile()
    # Run test
    PGConfig._configure_pg_hba_ambaridb_users(tf1.name, database_username)
    # Check results
    self.assertTrue(run_os_command_method.called)
    string_expected = self.get_file_string(self.get_samples_dir("configure_pg_hba_ambaridb_users1"))
    string_actual = self.get_file_string(tf1.name)
    self.assertEquals(string_expected, string_actual)
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch("__builtin__.raw_input")
  def test_servicename_regex(self, raw_input_method):

    ''' Test to make sure the service name can contain digits '''
    set_silent(False)
    raw_input_method.return_value = "OT100"
    result = OracleConfig._get_validated_service_name("ambari", 1)
    self.assertEqual("OT100", result, "Not accepting digits")
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch("__builtin__.raw_input")
  def test_dbname_regex(self, raw_input_method):

    ''' Test to make sure the service name can contain digits '''
    set_silent(False)
    raw_input_method.return_value = "OT100"
    result = LinuxDBMSConfig._get_validated_db_name("Database", "ambari")
    self.assertEqual("OT100", result, "Not accepting digits")
    pass


  @not_for_platform(PLATFORM_WINDOWS)
  def test_configure_pg_hba_postgres_user(self):

    tf1 = tempfile.NamedTemporaryFile()
    PGConfig.PG_HBA_CONF_FILE = tf1.name

    with open(PGConfig.PG_HBA_CONF_FILE, 'w') as fout:
      fout.write("\n")
      fout.write("local  all  all md5\n")
      fout.write("host  all   all 0.0.0.0/0  md5\n")
      fout.write("host  all   all ::/0 md5\n")

    PGConfig._configure_pg_hba_postgres_user()

    expected = self.get_file_string(self.get_samples_dir(
      "configure_pg_hba_ambaridb_users2"))
    result = self.get_file_string(PGConfig.PG_HBA_CONF_FILE)
    self.assertEqual(expected, result, "pg_hba_conf not processed")

    mode = oct(os.stat(PGConfig.PG_HBA_CONF_FILE)[stat.ST_MODE])
    str_mode = str(mode)[-4:]
    self.assertEqual("0644", str_mode, "Wrong file permissions")
    pass


  @patch("__builtin__.raw_input")
  def test_get_choice_string_input(self, raw_input_method):
    prompt = "blablabla"
    default = "default blablabla"
    firstChoice = set(['yes', 'ye', 'y'])
    secondChoice = set(['no', 'n'])
    # test first input
    raw_input_method.return_value = "Y"

    result = get_choice_string_input(prompt, default,
                                                   firstChoice, secondChoice)
    self.assertEquals(result, True)
    raw_input_method.reset_mock()
    # test second input

    raw_input_method.return_value = "N"

    result = get_choice_string_input(prompt, default,
                                                   firstChoice, secondChoice)
    self.assertEquals(result, False)

    raw_input_method.reset_mock()

    # test enter pressed

    raw_input_method.return_value = ""

    result = get_choice_string_input(prompt, default,
                                                   firstChoice, secondChoice)
    self.assertEquals(result, default)

    raw_input_method.reset_mock()

    # test wrong input
    list_of_return_values = ['yes', 'dsad', 'fdsfds']

    def side_effect(list):
      return list_of_return_values.pop()

    raw_input_method.side_effect = side_effect

    result = get_choice_string_input(prompt, default,
                                                   firstChoice, secondChoice)
    self.assertEquals(result, True)
    self.assertEquals(raw_input_method.call_count, 3)

    pass


  @patch("re.search")
  @patch("__builtin__.raw_input")
  @patch("getpass.getpass")
  def test_get_validated_string_input(self, get_pass_method,
                                 raw_input_method, re_search_method):
    prompt = "blabla"
    default = "default_pass"
    pattern = "pattern_pp"
    description = "blabla2"
    # check password input
    self.assertFalse(False, get_silent())
    is_pass = True
    get_pass_method.return_value = "dfdsfdsfds"

    result = get_validated_string_input(prompt, default,
                                                      pattern, description, is_pass)

    self.assertEquals(get_pass_method.return_value, result)
    get_pass_method.assure_called_once(prompt)
    self.assertFalse(raw_input_method.called)

    # check raw input
    get_pass_method.reset_mock()
    raw_input_method.reset_mock()
    is_pass = False
    raw_input_method.return_value = "dkf90ewuf0"

    result = get_validated_string_input(prompt, default,
                                                      pattern, description, is_pass)

    self.assertEquals(raw_input_method.return_value, result)
    self.assertFalse(get_pass_method.called)
    raw_input_method.assure_called_once(prompt)
    pass


  @not_for_platform(PLATFORM_WINDOWS)
  def test_get_pass_file_path(self):
    result = get_pass_file_path("/etc/ambari/conf_file", JDBC_PASSWORD_FILENAME)
    self.assertEquals("/etc/ambari/password.dat", result)
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(_ambari_server_, "setup_security")
  @patch("optparse.OptionParser")
  def test_main_test_setup_security(self, OptionParserMock,
                                    setup_security_method):
    opm = OptionParserMock.return_value
    options = MagicMock()
    args = ["setup-security"]
    opm.parse_args.return_value = (options, args)
    options.dbms = None
    options.sid_or_sname = "sid"
    setup_security_method.return_value = None

    _ambari_server_.mainBody()

    _ambari_server_.mainBody()
    self.assertTrue(setup_security_method.called)
    self.assertFalse(False, get_verbose())
    self.assertFalse(False, get_silent())
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(_ambari_server_, "setup_ambari_krb5_jaas")
  @patch.object(_ambari_server_, "setup_master_key")
  @patch("ambari_server.setupHttps.setup_component_https")
  @patch.object(_ambari_server_, "setup_https")
  @patch.object(_ambari_server_, "get_validated_string_input")
  def test_setup_security(self, get_validated_string_input_mock, setup_https_mock,
                          setup_component_https_mock, setup_master_key_mock,
                          setup_ambari_krb5_jaas_mock):

    args = {}
    get_validated_string_input_mock.return_value = '1'
    _ambari_server_.setup_security(args)
    self.assertTrue(setup_https_mock.called)

    get_validated_string_input_mock.return_value = '2'
    _ambari_server_.setup_security(args)
    self.assertTrue(setup_master_key_mock.called)

    get_validated_string_input_mock.return_value = '3'
    _ambari_server_.setup_security(args)
    self.assertTrue(setup_ambari_krb5_jaas_mock.called)
    pass


  @patch("re.sub")
  @patch("fileinput.FileInput")
  @patch("ambari_server.setupSecurity.get_validated_string_input")
  @patch("ambari_server.setupSecurity.search_file")
  @patch("os.path.exists")
  def test_setup_ambari_krb5_jaas(self, exists_mock, search_mock,
                                  get_validated_string_input_mock,
                                  fileinput_mock, re_sub_mock):

    search_mock.return_value = 'filepath'
    exists_mock.return_value = False

    # Negative case
    try:
      setup_ambari_krb5_jaas()
      self.fail("Should throw exception")
    except NonFatalException as fe:
      # Expected
      self.assertTrue("No jaas config file found at location" in fe.reason)
      pass

    # Positive case
    exists_mock.reset_mock()
    exists_mock.return_value = True
    get_validated_string_input_mock.side_effect = ['aaa@aaa.cnn',
                                                   'pathtokeytab']

    fileinput_mock.return_value = [ 'keyTab=xyz', 'principal=xyz' ]

    setup_ambari_krb5_jaas()

    self.assertTrue(fileinput_mock.called)
    self.assertTrue(re_sub_mock.called)
    self.assertTrue(re_sub_mock.call_args_list, [('aaa@aaa.cnn'),
                                                 ('pathtokeytab')])
    pass

  @patch("sys.exit")
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(_ambari_server_, "setup")
  @patch.object(_ambari_server_, "start")
  @patch.object(_ambari_server_, "stop")
  @patch.object(_ambari_server_, "reset")
  @patch("optparse.OptionParser")
  def test_main_test_setup(self, OptionParserMock, reset_method, stop_method,
                           start_method, setup_method, exit_mock):
    opm = OptionParserMock.return_value
    options = MagicMock()
    args = ["setup"]
    opm.parse_args.return_value = (options, args)

    options.dbms = None
    options.sid_or_sname = "sid"
    _ambari_server_.mainBody()

    self.assertTrue(setup_method.called)
    self.assertFalse(start_method.called)
    self.assertFalse(stop_method.called)
    self.assertFalse(reset_method.called)

    self.assertFalse(False, get_verbose())
    self.assertFalse(False, get_silent())

    setup_method.reset_mock()
    start_method.reset_mock()
    stop_method.reset_mock()
    reset_method.reset_mock()
    exit_mock.reset_mock()
    args = ["setup", "-v"]
    options = MagicMock()
    opm.parse_args.return_value = (options, args)
    options.dbms = None
    options.sid_or_sname = "sid"
    setup_method.side_effect = Exception("Unexpected error")
    try:
      _ambari_server_.mainBody()
    except Exception:
      self.assertTrue(True)
    self.assertTrue(setup_method.called)
    self.assertFalse(start_method.called)
    self.assertFalse(stop_method.called)
    self.assertFalse(reset_method.called)
    self.assertTrue(get_verbose())

    setup_method.reset_mock()
    start_method.reset_mock()
    stop_method.reset_mock()
    reset_method.reset_mock()
    exit_mock.reset_mock()
    args = ["setup"]
    options = MagicMock()
    opm.parse_args.return_value = (options, args)
    options.dbms = None
    options.sid_or_sname = "sid"
    options.verbose = False
    setup_method.side_effect = Exception("Unexpected error")
    _ambari_server_.mainBody()
    self.assertTrue(exit_mock.called)
    self.assertTrue(setup_method.called)
    self.assertFalse(start_method.called)
    self.assertFalse(stop_method.called)
    self.assertFalse(reset_method.called)
    self.assertFalse(get_verbose())

    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(_ambari_server_, "setup")
  @patch.object(_ambari_server_, "start")
  @patch.object(_ambari_server_, "stop")
  @patch.object(_ambari_server_, "reset")
  @patch("optparse.OptionParser")
  def test_main_test_start(self, optionParserMock, reset_method, stop_method,
                           start_method, setup_method):
    opm = optionParserMock.return_value
    options = MagicMock()
    args = ["setup"]
    opm.parse_args.return_value = (options, args)

    options.dbms = None
    options.sid_or_sname = "sname"
    _ambari_server_.mainBody()

    self.assertTrue(setup_method.called)
    self.assertFalse(start_method.called)
    self.assertFalse(stop_method.called)
    self.assertFalse(reset_method.called)

    self.assertFalse(False, get_verbose())
    self.assertFalse(False, get_silent())
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(_ambari_server_, "setup")
  @patch.object(_ambari_server_, "start")
  @patch.object(_ambari_server_, "stop")
  @patch.object(_ambari_server_, "reset")
  @patch("optparse.OptionParser")
  def test_main_test_start_debug_short(self, optionParserMock, reset_method, stop_method,
                                       start_method, setup_method):
    opm = optionParserMock.return_value
    options = MagicMock()
    args = ["start", "-g"]
    opm.parse_args.return_value = (options, args)

    options.dbms = None
    options.sid_or_sname = "sid"

    _ambari_server_.mainBody()

    self.assertFalse(setup_method.called)
    self.assertTrue(start_method.called)
    self.assertFalse(stop_method.called)
    self.assertFalse(reset_method.called)

    self.assertTrue(get_debug_mode())
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(_ambari_server_, "setup")
  @patch.object(_ambari_server_, "start")
  @patch.object(_ambari_server_, "stop")
  @patch.object(_ambari_server_, "reset")
  @patch("optparse.OptionParser")
  def test_main_test_start_debug_long(self, optionParserMock, reset_method, stop_method,
                                      start_method, setup_method):
    opm = optionParserMock.return_value
    options = MagicMock()
    args = ["start", "--debug"]
    opm.parse_args.return_value = (options, args)
    options.dbms = None
    options.sid_or_sname = "sid"

    _ambari_server_.mainBody()

    self.assertFalse(setup_method.called)
    self.assertTrue(start_method.called)
    self.assertFalse(stop_method.called)
    self.assertFalse(reset_method.called)

    self.assertTrue(get_debug_mode())
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(_ambari_server_, "setup")
  @patch.object(_ambari_server_, "start")
  @patch.object(_ambari_server_, "stop")
  @patch.object(_ambari_server_, "reset")
  @patch.object(_ambari_server_, "backup")
  @patch.object(_ambari_server_, "restore")
  @patch("optparse.OptionParser")
  def test_main_test_backup(self, optionParserMock, restore_mock, backup_mock, reset_method, stop_method,
                           start_method, setup_method):
    opm = optionParserMock.return_value
    options = MagicMock()
    args = ["backup"]
    opm.parse_args.return_value = (options, args)

    options.dbms = None
    options.sid_or_sname = "sname"
    _ambari_server_.mainBody()

    self.assertTrue(backup_mock.called)
    self.assertFalse(restore_mock.called)
    self.assertFalse(setup_method.called)
    self.assertFalse(start_method.called)
    self.assertFalse(stop_method.called)
    self.assertFalse(reset_method.called)

    self.assertFalse(False, get_verbose())
    self.assertFalse(False, get_silent())
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(_ambari_server_, "setup")
  @patch.object(_ambari_server_, "start")
  @patch.object(_ambari_server_, "stop")
  @patch.object(_ambari_server_, "reset")
  @patch.object(_ambari_server_, "backup")
  @patch.object(_ambari_server_, "restore")
  @patch("optparse.OptionParser")
  def test_main_test_restore(self, optionParserMock, restore_mock, backup_mock, reset_method, stop_method,
                            start_method, setup_method):
    opm = optionParserMock.return_value
    options = MagicMock()
    args = ["restore"]
    opm.parse_args.return_value = (options, args)

    options.dbms = None
    options.sid_or_sname = "sname"
    _ambari_server_.mainBody()

    self.assertTrue(restore_mock.called)
    self.assertFalse(backup_mock.called)
    self.assertFalse(setup_method.called)
    self.assertFalse(start_method.called)
    self.assertFalse(stop_method.called)
    self.assertFalse(reset_method.called)

    self.assertFalse(False, get_verbose())
    self.assertFalse(False, get_silent())
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(_ambari_server_, "setup")
  @patch.object(_ambari_server_, "start")
  @patch.object(_ambari_server_, "is_server_runing")
  @patch.object(_ambari_server_, "reset")
  @patch("optparse.OptionParser")
  def test_main_test_stop(self, optionParserMock, reset_method, is_server_runing_method,
                          start_method, setup_method):
    opm = optionParserMock.return_value
    options = MagicMock()
    del options.exit_message

    args = ["stop"]
    opm.parse_args.return_value = (options, args)

    is_server_runing_method.return_value = (False, None)

    options.dbms = None
    options.sid_or_sname = "sid"

    _ambari_server_.mainBody()

    self.assertFalse(setup_method.called)
    self.assertFalse(start_method.called)
    self.assertTrue(is_server_runing_method.called)
    self.assertFalse(reset_method.called)

    self.assertFalse(False, get_verbose())
    self.assertFalse(False, get_silent())

    self.assertTrue(options.exit_message is None)
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(_ambari_server_, "setup")
  @patch.object(_ambari_server_, "start")
  @patch.object(_ambari_server_, "stop")
  @patch.object(_ambari_server_, "reset")
  @patch("optparse.OptionParser")
  def test_main_test_reset(self, optionParserMock, reset_method, stop_method,
                           start_method, setup_method):
    opm = optionParserMock.return_value

    options = MagicMock()
    args = ["reset"]
    opm.parse_args.return_value = (options, args)
    options.dbms = None
    options.sid_or_sname = "sid"

    _ambari_server_.mainBody()

    self.assertFalse(setup_method.called)
    self.assertFalse(start_method.called)
    self.assertFalse(stop_method.called)
    self.assertTrue(reset_method.called)

    self.assertFalse(False, get_verbose())
    self.assertFalse(False, get_silent())
    pass


  @not_for_platform(PLATFORM_WINDOWS)
  def test_configure_postgresql_conf(self):
    tf1 = tempfile.NamedTemporaryFile()
    PGConfig.POSTGRESQL_CONF_FILE = tf1.name

    with open(PGConfig.POSTGRESQL_CONF_FILE, 'w') as f:
      f.write("#listen_addresses = '127.0.0.1'        #\n")
      f.write("#listen_addresses = '127.0.0.1'")

    PGConfig._configure_postgresql_conf()

    expected = self.get_file_string(self.get_samples_dir(
      "configure_postgresql_conf1"))
    result = self.get_file_string(PGConfig.POSTGRESQL_CONF_FILE)
    self.assertEqual(expected, result, "postgresql.conf not updated")

    mode = oct(os.stat(PGConfig.POSTGRESQL_CONF_FILE)[stat.ST_MODE])
    str_mode = str(mode)[-4:]
    self.assertEqual("0644", str_mode, "Wrong file permissions")
    pass


  @not_for_platform(PLATFORM_WINDOWS)
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(PGConfig, "_restart_postgres")
  @patch.object(PGConfig, "_get_postgre_status")
  @patch.object(PGConfig, "_configure_postgresql_conf")
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  def test_configure_postgres(self,
                              run_os_command_mock,
                              configure_postgresql_conf_mock,
                              get_postgre_status_mock,
                              restart_postgres_mock):
    args = MagicMock()
    properties = Properties()

    args.database_index = 0

    del args.dbms
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password
    del args.silent

    factory = DBMSConfigFactory()
    dbConfig = factory.create(args, properties)

    self.assertTrue(dbConfig.dbms, "postgres")
    self.assertTrue(dbConfig.persistence_type, "local")

    tf1 = tempfile.NamedTemporaryFile()
    tf2 = tempfile.NamedTemporaryFile()

    PGConfig.PG_HBA_CONF_FILE = tf1.name
    PGConfig.PG_HBA_CONF_FILE_BACKUP = tf2.name

    out = StringIO.StringIO()
    sys.stdout = out
    retcode, out1, err = dbConfig._configure_postgres()
    sys.stdout = sys.__stdout__
    self.assertEqual(0, retcode)
    self.assertEqual("Backup for pg_hba found, reconfiguration not required\n",
                     out.getvalue())
    tf2.close()

    get_postgre_status_mock.return_value = PGConfig.PG_STATUS_RUNNING, 0, "", ""
    run_os_command_mock.return_value = 0, "", ""
    restart_postgres_mock.return_value = 0, "", ""

    rcode, out, err = dbConfig._configure_postgres()

    self.assertTrue(os.path.isfile(PGConfig.PG_HBA_CONF_FILE_BACKUP),
                    "postgresql.conf backup not created")
    self.assertTrue(run_os_command_mock.called)
    mode = oct(os.stat(PGConfig.PG_HBA_CONF_FILE)[stat.ST_MODE])
    str_mode = str(mode)[-4:]
    self.assertEqual("0644", str_mode, "Wrong file permissions")
    self.assertTrue(configure_postgresql_conf_mock.called)
    self.assertEqual(0, rcode)

    os.unlink(PGConfig.PG_HBA_CONF_FILE_BACKUP)

    get_postgre_status_mock.return_value = "stopped", 0, "", ""
    rcode, out, err = dbConfig._configure_postgres()
    self.assertEqual(0, rcode)
    os.unlink(PGConfig.PG_HBA_CONF_FILE_BACKUP)
    sys.stdout = sys.__stdout__
    pass


  @not_for_platform(PLATFORM_WINDOWS)
  @patch("time.sleep")
  @patch("subprocess.Popen")
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  @patch.object(PGConfig, "_get_postgre_status")
  @patch("ambari_server.dbConfiguration_linux.print_info_msg")
  def test_restart_postgres(self, printInfoMsg_mock, get_postgre_status_mock,
                            run_os_command_mock, popenMock, sleepMock):
    p = MagicMock()
    p.poll.return_value = 0
    popenMock.return_value = p
    retcode, out, err = PGConfig._restart_postgres()
    self.assertEqual(0, retcode)

    p.poll.return_value = None
    get_postgre_status_mock.return_value = "stopped", 0, "", ""
    run_os_command_mock.return_value = (1, None, None)
    retcode, out, err = PGConfig._restart_postgres()
    self.assertEqual(1, retcode)
    pass


  @not_for_platform(PLATFORM_WINDOWS)
  @patch("shlex.split")
  @patch("subprocess.Popen")
  @patch("ambari_commons.os_linux.print_info_msg")
  def test_run_os_command(self, printInfoMsg_mock, popenMock, splitMock):

    p = MagicMock()
    p.communicate.return_value = (None, None)
    p.returncode = 3
    popenMock.return_value = p

    # with list arg
    cmd = ["exec", "arg"]
    run_os_command(cmd)
    self.assertFalse(splitMock.called)

    # with str arg
    resp = run_os_command("runme")
    self.assertEqual(3, resp[0])
    self.assertTrue(splitMock.called)
    pass

  @only_for_platform(PLATFORM_WINDOWS)
  @patch("shlex.split")
  @patch("subprocess.Popen")
  @patch("ambari_commons.os_windows.print_info_msg")
  def test_run_os_command(self, printInfoMsg_mock, popenMock, splitMock):

    p = MagicMock()
    p.communicate.return_value = (None, None)
    p.returncode = 3
    popenMock.return_value = p

    # with list arg
    cmd = ["exec", "arg"]
    run_os_command(cmd)
    self.assertFalse(splitMock.called)

    # with str arg
    resp = run_os_command("runme")
    self.assertEqual(3, resp[0])
    self.assertTrue(splitMock.called)
    pass


  @patch("ambari_server.serverConfiguration.get_conf_dir")
  @patch("ambari_server.serverConfiguration.search_file")
  def test_write_property(self, search_file_mock, get_conf_dir_mock):

    expected_content = "key1=val1\n"

    tf1 = tempfile.NamedTemporaryFile()
    search_file_mock.return_value = tf1.name
    write_property("key1", "val1")
    result = tf1.read()
    self.assertTrue(expected_content in result)
    pass


  @not_for_platform(PLATFORM_WINDOWS)
  @patch("ambari_server.dbConfiguration.decrypt_password_for_alias")
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  def test_setup_db(self, run_os_command_mock,
                    decrypt_password_for_alias_mock):
    args = MagicMock()
    del args.database_index
    del args.dbms
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password

    properties = Properties()
    properties.process_pair(JDBC_PASSWORD_PROPERTY, get_alias_string("mypwdalias"))

    decrypt_password_for_alias_mock.return_value = "password"
    dbms = PGConfig(args, properties, "local")

    self.assertTrue(decrypt_password_for_alias_mock.called)

    run_os_command_mock.return_value = (0, None, None)
    result = dbms._setup_db()
    self.assertTrue(run_os_command_mock.called)
    self.assertEqual((0, None, None), result)
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch("ambari_server.dbConfiguration.decrypt_password_for_alias")
  @patch("time.sleep")
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  def test_setup_db_connect_attempts_fail(self, run_os_command_mock,
                                          sleep_mock, decrypt_password_for_alias_mock):
    args = MagicMock()
    del args.database_index
    del args.dbms
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password

    properties = Properties()

    decrypt_password_for_alias_mock.return_value = "password"
    dbms = PGConfig(args, properties, "local")

    run_os_command_mock.side_effect = [(1, "error", "error"), (1, "error", "error"),
                                       (1, "error", "error")]
    result = dbms._setup_db()
    self.assertTrue(run_os_command_mock.called)
    self.assertEqual((1, 'error', 'error') , result)
    self.assertEqual(2, sleep_mock.call_count)
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch("ambari_server.dbConfiguration.decrypt_password_for_alias")
  @patch("time.sleep")
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  def test_setup_db_connect_attempts_success(self, run_os_command_mock,
                                             sleep_mock, decrypt_password_for_alias_mock):
    args = MagicMock()
    del args.database_index
    del args.dbms
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password

    properties = Properties()

    decrypt_password_for_alias_mock.return_value = "password"
    dbms = PGConfig(args, properties, "local")

    run_os_command_mock.side_effect = [(1, "error", "error"), (0, None, None),
                                       (0, None, None)]
    result = dbms._setup_db()
    self.assertTrue(run_os_command_mock.called)
    self.assertEqual((0, None, None) , result)
    self.assertEqual(1, sleep_mock.call_count)
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch("ambari_server.serverSetup.get_YN_input")
  @patch("ambari_server.serverSetup.run_os_command")
  def test_check_selinux(self, run_os_command_mock, getYNInput_mock):
    run_os_command_mock.return_value = (0, SE_STATUS_DISABLED,
                                        None)
    rcode = check_selinux()
    self.assertEqual(0, rcode)

    getYNInput_mock.return_value = True
    run_os_command_mock.return_value = (0, "enabled "
                                           + SE_MODE_ENFORCING,
                                        None)
    rcode = check_selinux()
    self.assertEqual(0, rcode)
    self.assertTrue(run_os_command_mock.called)
    self.assertTrue(getYNInput_mock.called)
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch("ambari_server.serverConfiguration.print_info_msg")
  def test_get_ambari_jars(self, printInfoMsg_mock):

    env = "/ambari/jars"
    os.environ[AMBARI_SERVER_LIB] = env
    result = get_ambari_jars()
    self.assertEqual(env, result)

    del os.environ[AMBARI_SERVER_LIB]
    result = get_ambari_jars()
    self.assertEqual("/usr/lib/ambari-server", result)
    self.assertTrue(printInfoMsg_mock.called)
    pass

  @only_for_platform(PLATFORM_WINDOWS)
  @patch("ambari_server.serverConfiguration.print_info_msg")
  def test_get_ambari_jars(self, printInfoMsg_mock):

    env = "/ambari/jars"
    os.environ[AMBARI_SERVER_LIB] = env
    result = get_ambari_jars()
    self.assertEqual(env, result)

    del os.environ[AMBARI_SERVER_LIB]
    result = get_ambari_jars()
    self.assertEqual("libs", result)
    self.assertTrue(printInfoMsg_mock.called)
    pass

  @patch("glob.glob")
  @patch("ambari_server.serverConfiguration.print_info_msg")
  def test_get_share_jars(self, printInfoMsg_mock, globMock):
    globMock.return_value = ["one", "two"]
    expected = "one:two:one:two:one:two"
    result = get_share_jars()
    self.assertEqual(expected, result)
    globMock.return_value = []
    expected = ""
    result = get_share_jars()
    self.assertEqual(expected, result)
    pass

  @patch("glob.glob")
  @patch("ambari_server.serverConfiguration.print_info_msg")
  @patch("ambari_server.serverConfiguration.get_ambari_properties")
  def test_get_ambari_classpath(self, get_ambari_properties_mock, printInfoMsg_mock, globMock):
    globMock.return_value = ["one"]
    result = get_ambari_classpath()
    self.assertTrue(get_ambari_jars() in result)
    self.assertTrue(get_share_jars() in result)
    globMock.return_value = []
    result = get_ambari_classpath()
    self.assertTrue(get_ambari_jars() in result)
    self.assertFalse(":" in result)
    pass

  @patch("ambari_server.serverConfiguration.print_info_msg")
  def test_get_conf_dir(self, printInfoMsg_mock):
    env = "/dummy/ambari/conf"
    os.environ[AMBARI_CONF_VAR] = env
    result = get_conf_dir()
    self.assertEqual(env, result)

    del os.environ[AMBARI_CONF_VAR]
    result = get_conf_dir()
    self.assertEqual("/etc/ambari-server/conf", result)
    pass

  def test_search_file(self):
    path = os.path.dirname(__file__)
    result = search_file(__file__, path)
    expected = os.path.abspath(__file__)
    self.assertEqual(expected, result)

    result = search_file("non_existent_file", path)
    self.assertEqual(None, result)
    pass

  @patch("ambari_server.serverConfiguration.search_file")
  def test_find_properties_file(self, search_file_mock):
    # Testing case when file is not found
    search_file_mock.return_value = None
    try:
      find_properties_file()
      self.fail("File not found'")
    except FatalException:
      # Expected
      pass
    self.assertTrue(search_file_mock.called)

    # Testing case when file is found
    value = MagicMock()
    search_file_mock.return_value = value
    result = find_properties_file()
    self.assertTrue(result is value)
    pass

  @patch("ambari_server.serverConfiguration.find_properties_file")
  @patch("__builtin__.open")
  @patch("ambari_server.serverConfiguration.Properties")
  def test_read_ambari_user(self, properties_mock, open_mock, find_properties_file_mock):
    open_mock.return_value = "dummy"
    find_properties_file_mock.return_value = "dummy"
    # Testing with defined user
    properties_mock.return_value.__getitem__.return_value = "dummy_user"
    user = read_ambari_user()
    self.assertEquals(user, "dummy_user")
    # Testing with undefined user
    properties_mock.return_value.__getitem__.return_value = None
    user = read_ambari_user()
    self.assertEquals(user, None)
    pass

  @patch("os.path.exists")
  @patch("ambari_server.setupSecurity.set_file_permissions")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.get_resources_location")
  @patch("ambari_server.setupSecurity.get_value_from_properties")
  @patch("os.mkdir")
  @patch("shutil.rmtree")
  @patch("ambari_commons.os_utils.print_info_msg")
  @patch("ambari_server.setupSecurity.change_owner")
  def test_adjust_directory_permissions(self, change_owner_mock, print_info_msg_mock, rmtree_mock, mkdir_mock,
                                        get_value_from_properties_mock, get_resources_location_mock,
                                        get_ambari_properties_mock, set_file_permissions_mock, exists_mock):
    # Testing boostrap dir wipe
    properties_mock = MagicMock()
    get_value_from_properties_mock.return_value = "dummy_bootstrap_dir"
    get_resources_location_mock.return_value = "dummy_resources_dir"
    exists_mock.return_value = False
    adjust_directory_permissions("user")
    self.assertEquals(rmtree_mock.call_args_list[0][0][0], os.path.join(os.getcwd(), "dummy_bootstrap_dir"))
    self.assertTrue(mkdir_mock.called)

    set_file_permissions_mock.reset_mock()
    change_owner_mock.reset_mock()
    # Test recursive calls
    old_adjust_owner_list = configDefaults.NR_ADJUST_OWNERSHIP_LIST
    old_change_owner_list = configDefaults.NR_CHANGE_OWNERSHIP_LIST
    try:
      configDefaults.NR_ADJUST_OWNERSHIP_LIST = [
        ( "/etc/ambari-server/conf", "755", "{0}", True ),
        ( "/etc/ambari-server/conf/ambari.properties", "644", "{0}", False )
      ]

      configDefaults.NR_CHANGE_OWNERSHIP_LIST = [
        ( "/etc/ambari-server", "{0}", True )
      ]

      adjust_directory_permissions("user")
      self.assertTrue(len(set_file_permissions_mock.call_args_list) ==
                      len(configDefaults.NR_ADJUST_OWNERSHIP_LIST))
      self.assertEquals(set_file_permissions_mock.call_args_list[0][0][3], True)
      self.assertEquals(set_file_permissions_mock.call_args_list[1][0][3], False)
      self.assertTrue(len(change_owner_mock.call_args_list) ==
                      len(configDefaults.NR_CHANGE_OWNERSHIP_LIST))
      self.assertEquals(change_owner_mock.call_args_list[0][0][2], True)
    finally:
      configDefaults.NR_ADJUST_OWNERSHIP_LIST = old_adjust_owner_list
      configDefaults.NR_CHANGE_OWNERSHIP_LIST = old_change_owner_list
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch("os.path.exists")
  @patch("ambari_commons.os_linux.os_run_os_command")
  @patch("ambari_commons.os_linux.print_warning_msg")
  @patch("ambari_commons.os_utils.print_info_msg")
  def test_set_file_permissions(self, print_info_msg_mock, print_warning_msg_mock,
                                run_os_command_mock, exists_mock):

    # Testing not existent file scenario
    exists_mock.return_value = False
    set_file_permissions("dummy-file", "dummy-mod",
                                       "dummy-user", False)
    self.assertFalse(run_os_command_mock.called)
    self.assertTrue(print_info_msg_mock.called)

    run_os_command_mock.reset_mock()
    print_warning_msg_mock.reset_mock()

    # Testing OK scenario
    exists_mock.return_value = True
    run_os_command_mock.side_effect = [(0, "", ""), (0, "", "")]
    set_file_permissions("dummy-file", "dummy-mod",
                                       "dummy-user", False)
    self.assertTrue(len(run_os_command_mock.call_args_list) == 2)
    self.assertFalse(print_warning_msg_mock.called)

    run_os_command_mock.reset_mock()
    print_warning_msg_mock.reset_mock()

    # Testing first command fail
    run_os_command_mock.side_effect = [(1, "", ""), (0, "", "")]
    set_file_permissions("dummy-file", "dummy-mod",
                                       "dummy-user", False)
    self.assertTrue(len(run_os_command_mock.call_args_list) == 2)
    self.assertTrue(print_warning_msg_mock.called)

    run_os_command_mock.reset_mock()
    print_warning_msg_mock.reset_mock()

    # Testing second command fail
    run_os_command_mock.side_effect = [(0, "", ""), (1, "", "")]
    set_file_permissions("dummy-file", "dummy-mod",
                                       "dummy-user", False)
    self.assertTrue(len(run_os_command_mock.call_args_list) == 2)
    self.assertTrue(print_warning_msg_mock.called)

    run_os_command_mock.reset_mock()
    print_warning_msg_mock.reset_mock()

    # Testing recursive operation

    exists_mock.return_value = True
    run_os_command_mock.side_effect = [(0, "", ""), (0, "", "")]
    set_file_permissions("dummy-file", "dummy-mod",
                                       "dummy-user", True)
    self.assertTrue(len(run_os_command_mock.call_args_list) == 2)
    self.assertTrue("-R" in run_os_command_mock.call_args_list[0][0][0])
    self.assertTrue("-R" in run_os_command_mock.call_args_list[1][0][0])
    self.assertFalse(print_warning_msg_mock.called)

    run_os_command_mock.reset_mock()
    print_warning_msg_mock.reset_mock()

    # Testing non-recursive operation

    exists_mock.return_value = True
    run_os_command_mock.side_effect = [(0, "", ""), (0, "", "")]
    set_file_permissions("dummy-file", "dummy-mod",
                                       "dummy-user", False)
    self.assertTrue(len(run_os_command_mock.call_args_list) == 2)
    self.assertFalse("-R" in run_os_command_mock.call_args_list[0][0][0])
    self.assertFalse("-R" in run_os_command_mock.call_args_list[1][0][0])
    self.assertFalse(print_warning_msg_mock.called)

    run_os_command_mock.reset_mock()
    print_warning_msg_mock.reset_mock()
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_server.serverSetup.get_validated_string_input")
  @patch("ambari_server.serverSetup.print_info_msg")
  @patch("ambari_server.serverSetup.print_warning_msg")
  @patch("ambari_server.serverSetup.run_os_command")
  def test_create_custom_user(self, run_os_command_mock, print_warning_msg_mock,
                              print_info_msg_mock, get_validated_string_input_mock):
    options = MagicMock()

    user = "dummy-user"
    get_validated_string_input_mock.return_value = user

    userChecks = AmbariUserChecks(options)

    # Testing scenario: absent user
    run_os_command_mock.side_effect = [(0, "", "")]
    result = userChecks._create_custom_user()
    self.assertFalse(print_warning_msg_mock.called)
    self.assertEquals(result, 0)
    self.assertEquals(userChecks.user, user)

    print_info_msg_mock.reset_mock()
    print_warning_msg_mock.reset_mock()
    run_os_command_mock.reset_mock()

    # Testing scenario: existing user
    run_os_command_mock.side_effect = [(9, "", "")]
    result = userChecks._create_custom_user()
    self.assertTrue("User dummy-user already exists" in str(print_info_msg_mock.call_args_list[1][0]))
    self.assertEquals(result, 0)
    self.assertEquals(userChecks.user, user)

    print_info_msg_mock.reset_mock()
    print_warning_msg_mock.reset_mock()
    run_os_command_mock.reset_mock()

    # Testing scenario: os command fail
    run_os_command_mock.side_effect = [(1, "", "")]
    result = userChecks._create_custom_user()
    self.assertTrue(print_warning_msg_mock.called)
    self.assertEquals(result, 1)
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_server.serverSetup.read_ambari_user")
  @patch("ambari_server.serverSetup.get_YN_input")
  @patch("ambari_server.serverSetup.get_validated_string_input")
  @patch("ambari_server.serverSetup.adjust_directory_permissions")
  @patch("ambari_server.serverSetup.run_os_command")
  @patch("ambari_server.serverSetup.print_error_msg")
  @patch("ambari_server.serverSetup.print_warning_msg")
  @patch("ambari_server.serverSetup.print_info_msg")
  def test_check_ambari_user(self, print_info_msg_mock, print_warning_msg_mock, print_error_msg_mock,
                             run_os_command_mock, adjust_directory_permissions_mock,
                             get_validated_string_input_mock, get_YN_input_mock, read_ambari_user_mock):

    options = MagicMock()

    run_os_command_mock.return_value = (0, "", "")

    # Scenario: user is already defined, user does not want to reconfigure it
    read_ambari_user_mock.return_value = "dummy-user"
    get_YN_input_mock.return_value = False
    result = check_ambari_user(options)
    self.assertTrue(get_YN_input_mock.called)
    self.assertFalse(get_validated_string_input_mock.called)
    self.assertFalse(run_os_command_mock.called)
    self.assertTrue(adjust_directory_permissions_mock.called)
    self.assertEqual(result[0], 0)

    get_YN_input_mock.reset_mock()
    get_validated_string_input_mock.reset_mock()
    run_os_command_mock.reset_mock()
    adjust_directory_permissions_mock.reset_mock()

    # Scenario: user is already defined, but user wants to reconfigure it

    read_ambari_user_mock.return_value = "dummy-user"
    get_validated_string_input_mock.return_value = "new-dummy-user"
    get_YN_input_mock.return_value = True
    result = check_ambari_user(options)
    self.assertTrue(get_YN_input_mock.called)
    self.assertTrue(result[2] == "new-dummy-user")
    self.assertTrue(get_validated_string_input_mock.called)
    self.assertTrue(adjust_directory_permissions_mock.called)
    self.assertEqual(result[0], 0)

    get_YN_input_mock.reset_mock()
    get_validated_string_input_mock.reset_mock()
    run_os_command_mock.reset_mock()
    adjust_directory_permissions_mock.reset_mock()

    # Negative scenario: user is already defined, but user wants
    # to reconfigure it, user creation failed

    read_ambari_user_mock.return_value = "dummy-user"
    run_os_command_mock.return_value = (1, "", "")
    get_YN_input_mock.return_value = True
    result = check_ambari_user(options)
    self.assertTrue(get_YN_input_mock.called)
    self.assertTrue(get_validated_string_input_mock.called)
    self.assertTrue(run_os_command_mock.called)
    self.assertFalse(adjust_directory_permissions_mock.called)
    self.assertEqual(result[0], 1)

    get_YN_input_mock.reset_mock()
    get_validated_string_input_mock.reset_mock()
    run_os_command_mock.reset_mock()
    adjust_directory_permissions_mock.reset_mock()

    # Scenario: user is not defined (setup process)
    read_ambari_user_mock.return_value = None
    get_YN_input_mock.return_value = True
    get_validated_string_input_mock.return_value = "dummy-user"
    run_os_command_mock.return_value = (0, "", "")
    result = check_ambari_user(options)
    self.assertTrue(get_YN_input_mock.called)
    self.assertTrue(get_validated_string_input_mock.called)
    self.assertTrue(run_os_command_mock.called)
    self.assertTrue(result[2] == "dummy-user")
    self.assertTrue(adjust_directory_permissions_mock.called)
    self.assertEqual(result[0], 0)

    get_YN_input_mock.reset_mock()
    get_validated_string_input_mock.reset_mock()
    run_os_command_mock.reset_mock()
    adjust_directory_permissions_mock.reset_mock()

    # Scenario: user is not defined (setup process), user creation failed

    read_ambari_user_mock.return_value = None
    get_YN_input_mock.return_value = True
    run_os_command_mock.return_value = (1, "", "")
    result = check_ambari_user(options)
    self.assertTrue(get_YN_input_mock.called)
    self.assertTrue(get_validated_string_input_mock.called)
    self.assertTrue(run_os_command_mock.called)
    self.assertFalse(adjust_directory_permissions_mock.called)
    self.assertEqual(result[0], 1)

    get_YN_input_mock.reset_mock()
    get_validated_string_input_mock.reset_mock()
    run_os_command_mock.reset_mock()
    adjust_directory_permissions_mock.reset_mock()

    # negative scenario: user is not defined (setup process), user creation failed

    read_ambari_user_mock.return_value = None
    get_YN_input_mock.return_value = True
    run_os_command_mock.return_value = (1, "", "")
    result = check_ambari_user(options)
    self.assertTrue(get_YN_input_mock.called)
    self.assertTrue(get_validated_string_input_mock.called)
    self.assertTrue(run_os_command_mock.called)
    self.assertFalse(adjust_directory_permissions_mock.called)
    self.assertEqual(result[0], 1)

    get_YN_input_mock.reset_mock()
    get_validated_string_input_mock.reset_mock()
    run_os_command_mock.reset_mock()
    adjust_directory_permissions_mock.reset_mock()

    # Scenario: user is not defined and left to be root
    read_ambari_user_mock.return_value = None
    get_YN_input_mock.return_value = False
    result = check_ambari_user(options)
    self.assertTrue(get_YN_input_mock.called)
    self.assertFalse(get_validated_string_input_mock.called)
    self.assertFalse(run_os_command_mock.called)
    self.assertTrue(result[2] == "root")
    self.assertTrue(adjust_directory_permissions_mock.called)
    self.assertEqual(result[0], 0)
    pass

  @patch("ambari_server.serverConfiguration.search_file")
  @patch("__builtin__.open")
  @patch("ambari_server.serverConfiguration.read_ambari_user")
  @patch("ambari_server.serverConfiguration.set_file_permissions")
  def test_store_password_file(self, set_file_permissions_mock,
                               read_ambari_user_mock, open_mock, search_file_mock):
    search_file_mock.return_value = "/etc/ambari-server/conf/ambari.properties"
    open_mock.return_value = MagicMock()
    store_password_file("password", "passfile")
    self.assertTrue(set_file_permissions_mock.called)
    pass

  @patch("subprocess.Popen")
  @patch.object(OSCheck, "get_os_family")
  @patch.object(OSCheck, "get_os_type")
  @patch.object(OSCheck, "get_os_major_version")
  def test_check_firewall_is_running(self, get_os_major_version_mock, get_os_type_mock, get_os_family_mock, popen_mock):

    get_os_major_version_mock.return_value = 18
    get_os_type_mock.return_value = OSConst.OS_FEDORA
    get_os_family_mock.return_value = OSConst.REDHAT_FAMILY

    firewall_obj = Firewall().getFirewallObject()
    p = MagicMock()
    p.communicate.return_value = ("active", "err")
    p.returncode = 0
    popen_mock.return_value = p
    self.assertEqual("Fedora18FirewallChecks", firewall_obj.__class__.__name__)
    self.assertTrue(firewall_obj.check_firewall())
    p.communicate.return_value = ("", "err")
    p.returncode = 3
    self.assertFalse(firewall_obj.check_firewall())
    self.assertEqual("err", firewall_obj.stderrdata)


    get_os_type_mock.return_value = OSConst.OS_UBUNTU
    get_os_family_mock.return_value = OSConst.UBUNTU_FAMILY

    firewall_obj = Firewall().getFirewallObject()
    p.communicate.return_value = ("Status: active", "err")
    p.returncode = 0
    self.assertEqual("UbuntuFirewallChecks", firewall_obj.__class__.__name__)
    self.assertTrue(firewall_obj.check_firewall())
    p.communicate.return_value = ("Status: inactive", "err")
    p.returncode = 0
    self.assertFalse(firewall_obj.check_firewall())
    self.assertEqual("err", firewall_obj.stderrdata)

    get_os_type_mock.return_value = ""
    get_os_family_mock.return_value = OSConst.SUSE_FAMILY

    firewall_obj = Firewall().getFirewallObject()
    p.communicate.return_value = ("### iptables", "err")
    p.returncode = 0
    self.assertEqual("SuseFirewallChecks", firewall_obj.__class__.__name__)
    self.assertTrue(firewall_obj.check_firewall())
    p.communicate.return_value = ("SuSEfirewall2 not active", "err")
    p.returncode = 0
    self.assertFalse(firewall_obj.check_firewall())
    self.assertEqual("err", firewall_obj.stderrdata)

    get_os_type_mock.return_value = ""
    get_os_family_mock.return_value = OSConst.REDHAT_FAMILY

    firewall_obj = Firewall().getFirewallObject()
    p.communicate.return_value = ("Table: filter", "err")
    p.returncode = 0
    self.assertEqual("FirewallChecks", firewall_obj.__class__.__name__)
    self.assertTrue(firewall_obj.check_firewall())
    p.communicate.return_value = ("", "err")
    p.returncode = 3
    self.assertFalse(firewall_obj.check_firewall())
    self.assertEqual("err", firewall_obj.stderrdata)
    pass

  @patch("ambari_server.setupHttps.get_validated_filepath_input")
  @patch("ambari_server.setupHttps.run_os_command")
  @patch("ambari_server.setupHttps.get_truststore_type")
  @patch("__builtin__.open")
  @patch("ambari_server.setupHttps.find_properties_file")
  @patch("ambari_server.setupHttps.run_component_https_cmd")
  @patch("ambari_server.setupHttps.get_delete_cert_command")
  @patch("ambari_server.setupHttps.get_truststore_password")
  @patch("ambari_server.setupHttps.get_truststore_path")
  @patch("ambari_server.setupHttps.get_YN_input")
  @patch("ambari_server.setupHttps.get_ambari_properties")
  @patch("ambari_server.setupHttps.find_jdk")
  def test_setup_component_https(self, find_jdk_mock, get_ambari_properties_mock, get_YN_input_mock,
                                 get_truststore_path_mock, get_truststore_password_mock,
                                 get_delete_cert_command_mock, run_component_https_cmd_mock,
                                 find_properties_file_mock, open_mock,
                                 get_truststore_type_mock, run_os_command_mock,
                                 get_validated_filepath_input_mock):
    out = StringIO.StringIO()
    sys.stdout = out
    component = "component"
    command = "command"
    property = "use_ssl"
    alias = "alias"
    #Silent mode
    set_silent(True)
    setup_component_https(component, command, property, alias)
    self.assertEqual('command is not enabled in silent mode.\n', out.getvalue())
    sys.stdout = sys.__stdout__
    #Verbouse mode and jdk_path is None
    set_silent(False)
    p = get_ambari_properties_mock.return_value
    # Use ssl
    p.get_property.side_effect = ["true"]
    # Dont disable ssl
    get_YN_input_mock.side_effect = [False]
    setup_component_https(component, command, property, alias)
    self.assertTrue(p.get_property.called)
    self.assertTrue(get_YN_input_mock.called)
    p.get_property.reset_mock()
    get_YN_input_mock.reset_mock()
    # Dont use ssl
    p.get_property.side_effect = ["false"]
    # Dont enable ssl
    get_YN_input_mock.side_effect = [False]
    setup_component_https(component, command, property, alias)
    self.assertTrue(p.get_property.called)
    self.assertTrue(get_YN_input_mock.called)
    p.get_property.reset_mock()
    get_YN_input_mock.reset_mock()
    # Cant find jdk
    find_jdk_mock.return_value = None
    try:
        setup_component_https(component, command, property, alias)
        self.fail("Should throw exception")
    except FatalException as fe:
        # Expected
        self.assertTrue('No JDK found, please run the "ambari-server setup" command to install a' +
                        ' JDK automatically or install any JDK manually to ' in fe.reason)
        pass
    #Verbouse mode and jdk_path is not None (use_https = true)
    find_jdk_mock.return_value = "/jdk_path"
    p.get_property.side_effect = ["true"]
    get_YN_input_mock.side_effect = [True]
    get_truststore_path_mock.return_value = "/truststore_path"
    get_truststore_password_mock.return_value = "/truststore_password"
    get_delete_cert_command_mock.return_value = "rm -f"
    setup_component_https(component, command, property, alias)

    self.assertTrue(p.process_pair.called)
    self.assertTrue(get_truststore_path_mock.called)
    self.assertTrue(get_truststore_password_mock.called)
    self.assertTrue(get_delete_cert_command_mock.called)
    self.assertTrue(find_properties_file_mock.called)
    self.assertTrue(open_mock.called)
    self.assertTrue(p.store.called)
    self.assertTrue(run_component_https_cmd_mock.called)

    p.process_pair.reset_mock()
    get_truststore_path_mock.reset_mock()
    get_truststore_password_mock.reset_mock()
    get_delete_cert_command_mock.reset_mock()
    find_properties_file_mock.reset_mock()
    open_mock.reset_mock()
    p.store.reset_mock()
    #Verbouse mode and jdk_path is not None (use_https = false) and import cert
    p.get_property.side_effect = ["false"]
    get_YN_input_mock.side_effect = [True]
    setup_component_https(component, command, property, alias)

    self.assertTrue(p.process_pair.called)
    self.assertTrue(get_truststore_type_mock.called)
    self.assertTrue(get_truststore_path_mock.called)
    self.assertTrue(get_truststore_password_mock.called)
    self.assertTrue(get_delete_cert_command_mock.called)
    self.assertTrue(find_properties_file_mock.called)
    self.assertTrue(open_mock.called)
    self.assertTrue(p.store.called)
    self.assertTrue(run_component_https_cmd_mock.called)
    self.assertTrue(run_os_command_mock.called)
    self.assertTrue(get_validated_filepath_input_mock.called)

    p.process_pair.reset_mock()
    get_truststore_type_mock.reset_mock()
    get_truststore_path_mock.reset_mock()
    get_truststore_password_mock.reset_mock()
    get_delete_cert_command_mock.reset_mock()
    find_properties_file_mock.reset_mock()
    open_mock.reset_mock()
    p.store.reset_mock()
    run_os_command_mock.reset_mock()
    get_validated_filepath_input_mock.reset_mock()
    pass

  @patch("ambari_server.setupHttps.adjust_directory_permissions")
  @patch("ambari_server.setupHttps.read_ambari_user")
  @patch("ambari_server.setupHttps.get_validated_string_input")
  @patch("ambari_server.setupHttps.find_properties_file")
  @patch("ambari_server.setupHttps.get_ambari_properties")
  @patch("ambari_server.setupHttps.import_cert_and_key_action")
  @patch("ambari_server.setupHttps.get_YN_input")
  @patch("__builtin__.open")
  @patch("ambari_server.setupHttps.is_root")
  @patch("ambari_server.setupHttps.is_valid_cert_host")
  @patch("ambari_server.setupHttps.is_valid_cert_exp")
  def test_setup_https(self, is_valid_cert_exp_mock, is_valid_cert_host_mock, \
                       is_root_mock, open_Mock, get_YN_input_mock, \
                       import_cert_and_key_action_mock,
                       get_ambari_properties_mock, \
                       find_properties_file_mock, \
                       get_validated_string_input_mock, read_ambari_user_method, \
                       adjust_directory_permissions_mock):

    is_valid_cert_exp_mock.return_value = True
    is_valid_cert_host_mock.return_value = True
    args = MagicMock()
    open_Mock.return_value = file
    p = get_ambari_properties_mock.return_value

    # Testing call under non-root
    is_root_mock.return_value = False
    try:
      setup_https(args)
      self.fail("Should throw exception")
    except FatalException as fe:
      # Expected
      self.assertTrue("root-level" in fe.reason)
      pass

    # Testing call under root
    is_root_mock.return_value = True
    read_ambari_user_method.return_value = "user"
    #Case #1: if client ssl is on and user didnt choose
    #disable ssl option and choose import certs and keys
    p.get_property.side_effect = ["key_dir", "5555", "6666", "true"]
    get_YN_input_mock.side_effect = [False, True]
    get_validated_string_input_mock.side_effect = ["4444"]
    get_property_expected = "[call('security.server.keys_dir'),\n" + \
                            " call('client.api.ssl.port'),\n" + \
                            " call('client.api.ssl.port'),\n call('api.ssl')]"
    process_pair_expected = "[call('client.api.ssl.port', '4444')]"
    set_silent(False)
    setup_https(args)

    self.assertTrue(p.process_pair.called)
    self.assertTrue(p.get_property.call_count == 4)
    self.assertEqual(str(p.get_property.call_args_list), get_property_expected)
    self.assertEqual(str(p.process_pair.call_args_list), process_pair_expected)
    self.assertTrue(p.store.called)
    self.assertTrue(import_cert_and_key_action_mock.called)

    p.process_pair.reset_mock()
    p.get_property.reset_mock()
    p.store.reset_mock()
    import_cert_and_key_action_mock.reset_mock()

    #Case #2: if client ssl is on and user choose to disable ssl option
    p.get_property.side_effect = ["key_dir", "", "true"]
    get_YN_input_mock.side_effect = [True]
    get_validated_string_input_mock.side_effect = ["4444"]
    get_property_expected = "[call('security.server.keys_dir'),\n" + \
                            " call('client.api.ssl.port'),\n call('api.ssl')]"
    process_pair_expected = "[call('api.ssl', 'false')]"
    setup_https(args)

    self.assertTrue(p.process_pair.called)
    self.assertTrue(p.get_property.call_count == 3)
    self.assertEqual(str(p.get_property.call_args_list), get_property_expected)
    self.assertEqual(str(p.process_pair.call_args_list), process_pair_expected)
    self.assertTrue(p.store.called)
    self.assertFalse(import_cert_and_key_action_mock.called)

    p.process_pair.reset_mock()
    p.get_property.reset_mock()
    p.store.reset_mock()
    import_cert_and_key_action_mock.reset_mock()

    #Case #3: if client ssl is off and user choose option
    #to import cert and keys
    p.get_property.side_effect = ["key_dir", "", None]
    get_YN_input_mock.side_effect = [True, True]
    get_validated_string_input_mock.side_effect = ["4444"]
    get_property_expected = "[call('security.server.keys_dir'),\n" + \
                            " call('client.api.ssl.port'),\n call('api.ssl')]"
    process_pair_expected = "[call('client.api.ssl.port', '4444')]"
    setup_https(args)

    self.assertTrue(p.process_pair.called)
    self.assertTrue(p.get_property.call_count == 3)
    self.assertEqual(str(p.get_property.call_args_list), get_property_expected)
    self.assertEqual(str(p.process_pair.call_args_list), process_pair_expected)
    self.assertTrue(p.store.called)
    self.assertTrue(import_cert_and_key_action_mock.called)

    p.process_pair.reset_mock()
    p.get_property.reset_mock()
    p.store.reset_mock()
    import_cert_and_key_action_mock.reset_mock()

    #Case #4: if client ssl is off and
    #user did not choose option to import cert and keys
    p.get_property.side_effect = ["key_dir", "", None]
    get_YN_input_mock.side_effect = [False]
    get_validated_string_input_mock.side_effect = ["4444"]
    get_property_expected = "[call('security.server.keys_dir'),\n" + \
                            " call('client.api.ssl.port'),\n call('api.ssl')]"
    process_pair_expected = "[]"
    setup_https(args)

    self.assertFalse(p.process_pair.called)
    self.assertTrue(p.get_property.call_count == 3)
    self.assertEqual(str(p.get_property.call_args_list), get_property_expected)
    self.assertEqual(str(p.process_pair.call_args_list), process_pair_expected)
    self.assertFalse(p.store.called)
    self.assertFalse(import_cert_and_key_action_mock.called)

    p.process_pair.reset_mock()
    p.get_property.reset_mock()
    p.store.reset_mock()
    import_cert_and_key_action_mock.reset_mock()

    #Case #5: if cert must be imported but didnt imported
    p.get_property.side_effect = ["key_dir", "", "false"]
    get_YN_input_mock.side_effect = [True]
    import_cert_and_key_action_mock.side_effect = [False]
    get_validated_string_input_mock.side_effect = ["4444"]
    get_property_expected = "[call('security.server.keys_dir'),\n" + \
                            " call('client.api.ssl.port'),\n call('api.ssl')]"
    process_pair_expected = "[call('client.api.ssl.port', '4444')]"
    self.assertFalse(setup_https(args))
    self.assertTrue(p.process_pair.called)
    self.assertTrue(p.get_property.call_count == 3)
    self.assertEqual(str(p.get_property.call_args_list), get_property_expected)
    self.assertEqual(str(p.process_pair.call_args_list), process_pair_expected)
    self.assertFalse(p.store.called)
    self.assertTrue(import_cert_and_key_action_mock.called)

    p.process_pair.reset_mock()
    p.get_property.reset_mock()
    p.store.reset_mock()
    import_cert_and_key_action_mock.reset_mock()

    #Case #6: if silent mode is enabled
    set_silent(True)
    try:
      setup_https(args)
      self.fail("Should throw exception")
    except NonFatalException as fe:
      self.assertTrue("setup-https is not enabled in silent mode" in fe.reason)

    p.process_pair.reset_mock()
    p.get_property.reset_mock()
    p.store.reset_mock()
    import_cert_and_key_action_mock.reset_mock()

    #Case #7: read property throw exception
    set_silent(False)
    find_properties_file_mock.return_value = "propertyFile"
    p.get_property.side_effect = KeyError("Failed to read property")
    try:
        setup_https(args)
        self.fail("Should throw exception")
    except FatalException as fe:
        self.assertTrue("Failed to read property" in fe.reason)
    pass

  @patch("ambari_server.setupHttps.import_cert_and_key")
  def test_import_cert_and_key_action(self, import_cert_and_key_mock):
    import_cert_and_key_mock.return_value = True
    properties = MagicMock()
    properties.get_property.side_effect = ["key_dir", "5555", "6666", "true"]
    properties.process_pair = MagicMock()
    expect_process_pair = "[call('client.api.ssl.cert_name', 'https.crt'),\n" + \
                          " call('client.api.ssl.key_name', 'https.key'),\n" + \
                          " call('api.ssl', 'true')]"
    import_cert_and_key_action("key_dir", properties)

    self.assertEqual(str(properties.process_pair.call_args_list), \
                     expect_process_pair)
    pass

  @patch("ambari_server.setupHttps.remove_file")
  @patch("ambari_server.setupHttps.copy_file")
  @patch("ambari_server.setupHttps.read_ambari_user")
  @patch("ambari_server.setupHttps.set_file_permissions")
  @patch("ambari_server.setupHttps.import_file_to_keystore")
  @patch("__builtin__.open")
  @patch("ambari_server.setupHttps.run_os_command")
  @patch("os.path.join")
  @patch("os.path.isfile")
  @patch("__builtin__.raw_input")
  @patch("ambari_server.setupHttps.get_validated_string_input")
  @patch("ambari_server.setupHttps.is_valid_cert_host")
  @patch("ambari_server.setupHttps.is_valid_cert_exp")
  def test_import_cert_and_key(self, is_valid_cert_exp_mock, \
                               is_valid_cert_host_mock, \
                               get_validated_string_input_mock, \
                               raw_input_mock, \
                               os_path_isfile_mock, \
                               os_path_join_mock, run_os_command_mock, \
                               open_mock, import_file_to_keystore_mock, \
                               set_file_permissions_mock, read_ambari_user_mock, copy_file_mock, \
                               remove_file_mock):
    is_valid_cert_exp_mock.return_value = True
    is_valid_cert_host_mock.return_value = True
    os_path_isfile_mock.return_value = True
    get_validated_string_input_mock.return_value = "password"
    raw_input_mock.side_effect = \
      ["cert_file_path", "key_file_path"]
    os_path_join_mock.side_effect = ["keystore_file_path", "keystore_file_path_tmp", \
                                     "pass_file_path", "pass_file_path_tmp", \
                                     "passin_file_path", "password_file_path", \
                                     "keystore_cert_file_path", \
                                     "keystore_cert_key_file_path", ]
    run_os_command_mock.return_value = (0, "", "")
    om = open_mock.return_value
    expect_import_file_to_keystore = "[call('keystore_file_path_tmp'," + \
                                     " 'keystore_file_path'),\n" + \
                                     " call('pass_file_path_tmp'," + \
                                     " 'pass_file_path'),\n" + \
                                     " call('cert_file_path'," + \
                                     " 'keystore_cert_file_path'),\n" + \
                                     " call('key_file_path'," + \
                                     " 'keystore_cert_key_file_path')]"

    import_cert_and_key("key_dir")
    self.assertTrue(raw_input_mock.call_count == 2)
    self.assertTrue(get_validated_string_input_mock.called)
    self.assertEqual(os_path_join_mock.call_count, 8)
    self.assertTrue(set_file_permissions_mock.call_count == 1)
    self.assertEqual(str(import_file_to_keystore_mock.call_args_list), \
                     expect_import_file_to_keystore)
    pass

  @patch("ambari_server.setupHttps.remove_file")
  @patch("ambari_server.setupHttps.copy_file")
  @patch("ambari_server.setupHttps.generate_random_string")
  @patch("ambari_server.setupHttps.read_ambari_user")
  @patch("ambari_server.setupHttps.set_file_permissions")
  @patch("ambari_server.setupHttps.import_file_to_keystore")
  @patch("__builtin__.open")
  @patch("ambari_server.setupHttps.run_os_command")
  @patch("os.path.join")
  @patch("ambari_server.setupHttps.get_validated_filepath_input")
  @patch("ambari_server.setupHttps.get_validated_string_input")
  @patch("ambari_server.setupHttps.is_valid_cert_host")
  @patch("ambari_server.setupHttps.is_valid_cert_exp")
  def test_import_cert_and_key_with_empty_password(self, \
                                                   is_valid_cert_exp_mock, is_valid_cert_host_mock,
                                                   get_validated_string_input_mock, get_validated_filepath_input_mock, \
                                                   os_path_join_mock, run_os_command_mock, open_mock, \
                                                   import_file_to_keystore_mock, set_file_permissions_mock,
                                                   read_ambari_user_mock, generate_random_string_mock, copy_file_mock, \
                                                   remove_file_mock):

    is_valid_cert_exp_mock.return_value = True
    is_valid_cert_host_mock.return_value = True
    get_validated_string_input_mock.return_value = ""
    get_validated_filepath_input_mock.side_effect = \
      ["cert_file_path", "key_file_path"]
    os_path_join_mock.side_effect = ["keystore_file_path", "keystore_file_path_tmp", \
                                     "pass_file_path", "pass_file_path_tmp", \
                                     "passin_file_path", "password_file_path", \
                                     "keystore_cert_file_path", \
                                     "keystore_cert_key_file_path", ]
    run_os_command_mock.return_value = (0, "", "")

    expect_import_file_to_keystore = "[call('keystore_file_path_tmp'," + \
                                     " 'keystore_file_path'),\n" + \
                                     " call('pass_file_path_tmp'," + \
                                     " 'pass_file_path'),\n" + \
                                     " call('cert_file_path'," + \
                                     " 'keystore_cert_file_path'),\n" + \
                                     " call('key_file_path.secured'," + \
                                     " 'keystore_cert_key_file_path')]"

    import_cert_and_key("key_dir")
    self.assertEquals(get_validated_filepath_input_mock.call_count, 2)
    self.assertTrue(get_validated_string_input_mock.called)
    self.assertEquals(os_path_join_mock.call_count, 8)
    self.assertEquals(set_file_permissions_mock.call_count, 1)
    self.assertEqual(str(import_file_to_keystore_mock.call_args_list), \
                     expect_import_file_to_keystore)
    self.assertTrue(generate_random_string_mock.called)
    pass

  @patch("__builtin__.open")
  @patch("ambari_server.setupHttps.copy_file")
  @patch("ambari_server.setupHttps.is_root")
  @patch("ambari_server.setupHttps.read_ambari_user")
  @patch("ambari_server.setupHttps.set_file_permissions")
  @patch("ambari_server.setupHttps.import_file_to_keystore")
  @patch("ambari_server.setupHttps.run_os_command")
  @patch("os.path.join")
  @patch("ambari_server.setupHttps.get_validated_filepath_input")
  @patch("ambari_server.setupHttps.get_validated_string_input")
  def test_import_cert_and_key_with_incorrect_password(self,
                                                       get_validated_string_input_mock, \
                                                       get_validated_filepath_input_mock, \
                                                       os_path_join_mock, \
                                                       run_os_command_mock, \
                                                       import_file_to_keystore_mock, \
                                                       set_file_permissions_mock, \
                                                       read_ambari_user_mock, \
                                                       is_root_mock, \
                                                       copy_file_mock, \
                                                       open_mock):
    get_validated_string_input_mock.return_value = "incorrect_password"
    get_validated_filepath_input_mock.return_value = 'filename'
    open_mock.return_value = MagicMock()

    os_path_join_mock.return_value = ''
    is_root_mock.return_value = True


    #provided password doesn't match, openssl command returns an error
    run_os_command_mock.return_value = (1, "", "Some error message")

    self.assertFalse(import_cert_and_key_action(*["key_dir", None]))
    self.assertFalse(import_cert_and_key("key_dir"))
    pass

  def test_is_valid_cert_exp(self):
    #No data in certInfo
    certInfo = {}
    is_valid = is_valid_cert_exp(certInfo)
    self.assertFalse(is_valid)

    #Issued in future
    issuedOn = (datetime.datetime.now() + datetime.timedelta(hours=1000)).strftime(SSL_DATE_FORMAT)
    expiresOn = (datetime.datetime.now() + datetime.timedelta(hours=2000)).strftime(SSL_DATE_FORMAT)
    certInfo = {NOT_BEFORE_ATTR: issuedOn,
                NOT_AFTER_ATTR: expiresOn}
    is_valid = is_valid_cert_exp(certInfo)
    self.assertFalse(is_valid)

    #Was expired
    issuedOn = (datetime.datetime.now() - datetime.timedelta(hours=2000)).strftime(SSL_DATE_FORMAT)
    expiresOn = (datetime.datetime.now() - datetime.timedelta(hours=1000)).strftime(SSL_DATE_FORMAT)
    certInfo = {NOT_BEFORE_ATTR: issuedOn,
                NOT_AFTER_ATTR: expiresOn}
    is_valid = is_valid_cert_exp(certInfo)
    self.assertFalse(is_valid)

    #Valid
    issuedOn = (datetime.datetime.now() - datetime.timedelta(hours=2000)).strftime(SSL_DATE_FORMAT)
    expiresOn = (datetime.datetime.now() + datetime.timedelta(hours=1000)).strftime(SSL_DATE_FORMAT)
    certInfo = {NOT_BEFORE_ATTR: issuedOn,
                NOT_AFTER_ATTR: expiresOn}
    is_valid = is_valid_cert_exp(certInfo)
    self.assertTrue(is_valid)
    pass

  @patch("ambari_server.setupHttps.get_fqdn")
  def test_is_valid_cert_host(self, get_fqdn_mock):

    #No data in certInfo
    certInfo = {}
    is_valid = is_valid_cert_host(certInfo)
    self.assertFalse(is_valid)

    #Failed to get FQDN
    get_fqdn_mock.return_value = None
    is_valid = is_valid_cert_host(certInfo)
    self.assertFalse(is_valid)

    #FQDN and Common name in certificated don't correspond
    get_fqdn_mock.return_value = 'host1'
    certInfo = {COMMON_NAME_ATTR: 'host2'}
    is_valid = is_valid_cert_host(certInfo)
    self.assertFalse(is_valid)

    #FQDN and Common name in certificated correspond
    get_fqdn_mock.return_value = 'host1'
    certInfo = {COMMON_NAME_ATTR: 'host1'}
    is_valid = is_valid_cert_host(certInfo)
    self.assertTrue(is_valid)
    pass

  @patch("ambari_server.setupHttps.get_ambari_properties")
  def test_is_valid_https_port(self, get_ambari_properties_mock):

    #No ambari.properties
    get_ambari_properties_mock.return_value = -1
    is_valid = is_valid_https_port(1111)
    self.assertEqual(is_valid, False)

    #User entered port used by one way auth
    portOneWay = "1111"
    portTwoWay = "2222"
    validPort = "3333"
    get_ambari_properties_mock.return_value = {SRVR_ONE_WAY_SSL_PORT_PROPERTY: portOneWay,
                                               SRVR_TWO_WAY_SSL_PORT_PROPERTY: portTwoWay}
    is_valid = is_valid_https_port(portOneWay)
    self.assertEqual(is_valid, False)

    #User entered port used by two way auth
    is_valid = is_valid_https_port(portTwoWay)
    self.assertEqual(is_valid, False)

    #User entered valid port
    get_ambari_properties_mock.return_value = {SRVR_ONE_WAY_SSL_PORT_PROPERTY: portOneWay,
                                               SRVR_TWO_WAY_SSL_PORT_PROPERTY: portTwoWay}
    is_valid = is_valid_https_port(validPort)
    self.assertEqual(is_valid, True)
    pass

  @patch("socket.getfqdn")
  @patch("urllib2.urlopen")
  @patch("ambari_server.setupHttps.get_ambari_properties")
  def test_get_fqdn(self, get_ambari_properties_mock, url_open_mock, getfqdn_mock):
    #No ambari.properties
    get_ambari_properties_mock.return_value = -1
    fqdn = get_fqdn()
    self.assertEqual(fqdn, None)

    #Check mbari_server.GET_FQDN_SERVICE_URL property name (AMBARI-2612)
    #property name should be server.fqdn.service.url
    self.assertEqual(GET_FQDN_SERVICE_URL, "server.fqdn.service.url")

    #Read FQDN from service
    p = MagicMock()
    p[GET_FQDN_SERVICE_URL] = 'someurl'
    get_ambari_properties_mock.return_value = p

    u = MagicMock()
    host = 'host1.domain.com'
    u.read.return_value = host
    url_open_mock.return_value = u

    fqdn = get_fqdn()
    self.assertEqual(fqdn, host)

    #Failed to read FQDN from service, getting from socket
    u.reset_mock()
    u.side_effect = Exception("Failed to read FQDN from service")
    getfqdn_mock.return_value = host
    fqdn = get_fqdn()
    self.assertEqual(fqdn, host)
    pass

  def test_get_ulimit_open_files(self):
    # 1 - No ambari.properties
    p = Properties()

    open_files = get_ulimit_open_files(p)
    self.assertEqual(open_files, ULIMIT_OPEN_FILES_DEFAULT)

    # 2 - With ambari.properties - ok
    prop_value = 65000
    p.process_pair(ULIMIT_OPEN_FILES_KEY, str(prop_value))
    open_files = get_ulimit_open_files(p)
    self.assertEqual(open_files, 65000)

    # 2 - With ambari.properties - default
    tf1 = tempfile.NamedTemporaryFile()
    prop_value = 0
    p.process_pair(ULIMIT_OPEN_FILES_KEY, str(prop_value))
    open_files = get_ulimit_open_files(p)
    self.assertEqual(open_files, ULIMIT_OPEN_FILES_DEFAULT)
    pass

  @patch("ambari_server.setupHttps.run_os_command")
  def test_get_cert_info(self, run_os_command_mock):
    # Error running openssl command
    path = 'path/to/certificate'
    run_os_command_mock.return_value = -1, None, None
    cert_info = get_cert_info(path)
    self.assertEqual(cert_info, None)

    #Empty result of openssl command
    run_os_command_mock.return_value = 0, None, None
    cert_info = get_cert_info(path)
    self.assertEqual(cert_info, None)

    #Positive scenario
    notAfter = 'Jul  3 14:12:57 2014 GMT'
    notBefore = 'Jul  3 14:12:57 2013 GMT'
    attr1_key = 'A'
    attr1_value = 'foo'
    attr2_key = 'B'
    attr2_value = 'bar'
    attr3_key = 'CN'
    attr3_value = 'host.domain.com'
    subject_pattern = '/{attr1_key}={attr1_value}/{attr2_key}={attr2_value}/{attr3_key}={attr3_value}'
    subject = subject_pattern.format(attr1_key=attr1_key, attr1_value=attr1_value,
                                     attr2_key=attr2_key, attr2_value=attr2_value,
                                     attr3_key=attr3_key, attr3_value=attr3_value)
    out_pattern = """
notAfter={notAfter}
notBefore={notBefore}
subject={subject}
-----BEGIN CERTIFICATE-----
MIIFHjCCAwYCCQDpHKOBI+Lt0zANBgkqhkiG9w0BAQUFADBRMQswCQYDVQQGEwJV
...
5lqd8XxOGSYoMOf+70BLN2sB
-----END CERTIFICATE-----
    """
    out = out_pattern.format(notAfter=notAfter, notBefore=notBefore, subject=subject)
    run_os_command_mock.return_value = 0, out, None
    cert_info = get_cert_info(path)
    self.assertEqual(cert_info['notAfter'], notAfter)
    self.assertEqual(cert_info['notBefore'], notBefore)
    self.assertEqual(cert_info['subject'], subject)
    self.assertEqual(cert_info[attr1_key], attr1_value)
    self.assertEqual(cert_info[attr2_key], attr2_value)
    self.assertEqual(cert_info[attr3_key], attr3_value)
    pass

  @patch("__builtin__.raw_input")
  def test_get_validated_string_input(self, raw_input_mock):
    prompt = 'prompt'
    default_value = 'default'
    description = 'desc'
    validator = MagicMock()
    validator.return_value = True
    inputed_value1 = 'val1'
    inputed_value2 = 'val2'
    raw_input_mock.return_value = inputed_value1
    input = get_validated_string_input(prompt, default_value, None,
                                                     description, False, False, validator)
    self.assertTrue(validator.called)
    self.assertEqual(inputed_value1, input)

    validator.side_effect = [False, True]
    raw_input_mock.side_effect = [inputed_value1, inputed_value2]
    input = get_validated_string_input(prompt, default_value, None,
                                                     description, False, False, validator)
    self.assertEqual(inputed_value2, input)
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_server.serverUtils.run_os_command")
  @patch("__builtin__.open")
  @patch("os.path.exists")
  def test_is_server_runing(self, os_path_exists_mock, open_mock, \
                            run_os_command_mock):
    os_path_exists_mock.return_value = True
    f = open_mock.return_value
    f.readline.return_value = "111"
    run_os_command_mock.return_value = 0, "", ""
    status, pid = is_server_runing()
    self.assertTrue(status)
    self.assertEqual(111, pid)
    os_path_exists_mock.return_value = False
    status, pid = is_server_runing()
    self.assertFalse(status)
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_server.serverUtils.run_os_command")
  @patch("__builtin__.open")
  @patch("os.path.exists")
  def test_is_server_runing_bad_file(self, os_path_exists_mock, open_mock, \
                            run_os_command_mock):
    os_path_exists_mock.return_value = True
    f = open_mock.return_value
    f.readline.return_value = "" # empty file content
    run_os_command_mock.return_value = 0, "", ""
    self.assertRaises(NonFatalException, is_server_runing)

    open_mock.side_effect = IOError('[Errno 13] Permission denied: /var/run/ambari-server/ambari-server.pid')
    self.assertRaises(FatalException, is_server_runing)
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("os.path.exists")
  @patch("os.makedirs")
  @patch("os.chdir")
  @patch("ambari_server.serverSetup.run_os_command")
  def test_install_jdk(self, run_os_command_mock, os_chdir_mock, os_makedirs_mock, os_path_exists_mock):
    run_os_command_mock.return_value = 1, "", ""
    os_path_exists_mock.return_value = False
    failed = False
    try:
      jdkSetup = JDKSetup()
      jdkSetup._install_jdk(MagicMock(), MagicMock())
      self.fail("Exception was not rised!")
    except FatalException:
      failed = True
    self.assertTrue(failed)
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_server.serverSetup.read_ambari_user")
  @patch("os.stat")
  @patch("os.path.isfile")
  @patch("os.path.exists")
  @patch("os.chdir")
  @patch("ambari_server.serverSetup.expand_jce_zip_file")
  @patch("ambari_server.serverSetup.force_download_file")
  @patch("ambari_server.serverSetup.get_YN_input")
  @patch("ambari_server.serverSetup.run_os_command")
  @patch("ambari_server.serverSetup.update_properties")
  @patch("ambari_server.serverSetup.get_validated_string_input")
  @patch("ambari_server.serverSetup.print_info_msg")
  @patch("ambari_server.serverSetup.validate_jdk")
  @patch("ambari_server.serverSetup.get_JAVA_HOME")
  @patch("ambari_server.serverSetup.get_ambari_properties")
  @patch("shutil.copyfile")
  @patch("sys.exit")
  def test_download_jdk(self, exit_mock, copyfile_mock, get_ambari_properties_mock, get_JAVA_HOME_mock, \
                        validate_jdk_mock, print_info_msg_mock, get_validated_string_input_mock, update_properties_mock, \
                        run_os_command_mock, get_YN_input_mock, force_download_file_mock, expand_jce_zip_file_mock,
                        os_chdir_mock, path_existsMock, path_isfileMock, statMock, read_ambari_user_mock):
    args = MagicMock()
    args.java_home = "somewhere"
    args.silent = False

    p = Properties()
    p.process_pair("java.releases", "jdk1")
    p.process_pair("jdk1.desc", "JDK name")
    p.process_pair("jdk1.url", "http://somewhere/somewhere.tar.gz")
    p.process_pair("jdk1.dest-file", "somewhere.tar.gz")
    p.process_pair("jdk1.jcpol-url", "http://somewhere/some-jcpol.tar.gz")
    p.process_pair("jdk1.jcpol-file", "some-jcpol.tar.gz")
    p.process_pair("jdk1.home", "/jdk1")
    p.process_pair("jdk1.re", "(jdk.*)/jre")

    validate_jdk_mock.return_value = False
    path_existsMock.return_value = False
    get_JAVA_HOME_mock.return_value = False
    read_ambari_user_mock.return_value = "ambari"
    get_ambari_properties_mock.return_value = p
    # Test case: ambari.properties not found
    try:
      download_and_install_jdk(args)
      self.fail("Should throw exception because of not found ambari.properties")
    except FatalException:
      # Expected
      self.assertTrue(get_ambari_properties_mock.called)
      pass

    # Test case: JDK already exists
    args.java_home = None
    args.jdk_location = None
    get_JAVA_HOME_mock.return_value = "some_jdk"
    validate_jdk_mock.return_value = True
    get_YN_input_mock.return_value = False
    path_existsMock.return_value = False
    run_os_command_mock.return_value = 0, "", ""
    rcode = download_and_install_jdk(args)
    self.assertEqual(0, rcode)

    # Test case: java home setup
    args.java_home = "somewhere"
    validate_jdk_mock.return_value = True
    path_existsMock.return_value = False
    get_JAVA_HOME_mock.return_value = None
    rcode = download_and_install_jdk(args)
    self.assertEqual(0, rcode)
    self.assertTrue(update_properties_mock.called)

    # Test case: JDK file does not exist, property not defined
    validate_jdk_mock.return_value = False
    path_existsMock.return_value = False
    get_ambari_properties_mock.return_value = p
    p.removeProp("jdk1.url")
    try:
      download_and_install_jdk(args)
      self.fail("Should throw exception")
    except FatalException:
      # Expected
      pass

    # Test case: JDK file does not exist, HTTP response does not
    # contain Content-Length
    p.process_pair("jdk1.url", "http://somewhere/somewhere.tar.gz")
    validate_jdk_mock.return_value = False
    path_existsMock.return_value = False
    get_YN_input_mock.return_value = True
    get_validated_string_input_mock.return_value = "1"
    run_os_command_mock.return_value = (0, "Wrong out", None)
    try:
      download_and_install_jdk(args)
      self.fail("Should throw exception")
    except FatalException:
      # Expected
      pass

    # Successful JDK download
    args.java_home = None
    validate_jdk_mock.return_value = False
    path_existsMock.reset_mock()
    path_existsMock.side_effect = [True, False, True, False]
    path_isfileMock.return_value = False
    args.jdk_location = None
    run_os_command_mock.return_value = (0, "Creating jdk1/jre", None)
    statResult = MagicMock()
    statResult.st_size = 32000
    statMock.return_value = statResult
    try:
      rcode = download_and_install_jdk(args)
    except Exception, e:
      raise
    self.assertEqual(0, rcode)

    # Test case: not accept the license"
    get_YN_input_mock.return_value = False
    path_existsMock.reset_mock()
    path_existsMock.side_effect = [True, False, True, False]
    download_and_install_jdk(args)
    self.assertTrue(exit_mock.called)

    # Test case: jdk is already installed, ensure that JCE check is skipped if -j option is not supplied.
    args.jdk_location = None
    get_JAVA_HOME_mock.return_value = "some_jdk"
    validate_jdk_mock.return_value = True
    get_YN_input_mock.return_value = False
    path_existsMock.reset_mock()
    path_existsMock.side_effect = [True, False, True, False]
    force_download_file_mock.reset_mock()
    with patch("ambari_server.serverSetup.JDKSetup._download_jce_policy") as download_jce_policy_mock:
      rcode = download_and_install_jdk(args)
      self.assertFalse(download_jce_policy_mock.called)
      self.assertFalse(force_download_file_mock.called)

    # Test case: Update JAVA_HOME location using command: ambari-server setup -j %NEW_LOCATION%
    update_properties_mock.reset_mock()
    args.java_home = "somewhere"
    validate_jdk_mock.return_value = True
    path_existsMock.reset_mock()
    path_existsMock.side_effect = [True, False, True, False]
    get_JAVA_HOME_mock.return_value = "some_jdk"
    path_isfileMock.return_value = True
    download_and_install_jdk(args)
    self.assertTrue(update_properties_mock.call_count == 1)

    # Test case: Negative test case JAVA_HOME location should not be updated if -j option is supplied and
    # jce_policy file already exists in resources dir.
    #write_property_mock.reset_mock()
    #args.java_home = "somewhere"
    #path_existsMock.side_effect = None
    #path_existsMock.return_value = True
    #get_JAVA_HOME_mock.return_value = "some_jdk"
    #try:
    #  download_and_install_jdk(args)
    #  self.fail("Should throw exception")
    #except FatalException as fe:
    # Expected
    #  self.assertFalse(write_property_mock.called)

    # Test case: Setup ambari-server first time, Custom JDK selected, JDK exists
    args.java_home = None
    args.jdk_location = None
    validate_jdk_mock.return_value = False
    update_properties_mock.reset_mock()
    path_existsMock.reset_mock()
    path_existsMock.side_effect = [True, True, True, True]
    get_validated_string_input_mock.return_value = "2"
    get_JAVA_HOME_mock.return_value = None
    rcode = download_and_install_jdk(args)
    self.assertEqual(0, rcode)
    self.assertTrue(update_properties_mock.called)

    # Test case: Setup ambari-server first time, Custom JDK selected, JDK not exists
    update_properties_mock.reset_mock()
    validate_jdk_mock.return_value = False
    path_existsMock.reset_mock()
    path_existsMock.side_effect = [True, False, True, False]
    get_validated_string_input_mock.return_value = "2"
    get_JAVA_HOME_mock.return_value = None
    try:
      download_and_install_jdk(args)
      self.fail("Should throw exception")
    except FatalException as fe:
      # Expected
      pass

    # Test when custom java home exists but java binary file doesn't exist
    args.java_home = None
    validate_jdk_mock.return_value = False
    path_isfileMock.return_value = False
    update_properties_mock.reset_mock()
    path_existsMock.reset_mock()
    path_existsMock.side_effect = [True, False, True, False]
    get_validated_string_input_mock.return_value = "2"
    get_JAVA_HOME_mock.return_value = None
    flag = False
    try:
      download_and_install_jdk(args)
      self.fail("Should throw exception")
    except FatalException as fe:
      # Expected
      flag = True
      pass
    self.assertTrue(flag)

    #Test case: Setup ambari-server with java home passed. Path to java home doesn't exist
    args.java_home = "somewhere"
    validate_jdk_mock.return_value = False
    path_existsMock.reset_mock()
    path_existsMock.side_effect = [True, False, True, False]
    try:
      download_and_install_jdk(args)
      self.fail("Should throw exception")
    except FatalException as fe:
      self.assertTrue("Path to java home somewhere or java binary file does not exists" in fe.reason)
      pass
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  def test_get_postgre_status(self, run_os_command_mock):

    run_os_command_mock.return_value = (1, "running", None)
    pg_status, retcode, out, err = PGConfig._get_postgre_status()
    self.assertEqual("running", pg_status)

    run_os_command_mock.return_value = (1, "wrong", None)
    pg_status, retcode, out, err = PGConfig._get_postgre_status()
    self.assertEqual(None, pg_status)
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch("time.sleep")
  @patch("subprocess.Popen")
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  @patch.object(PGConfig, "_get_postgre_status")
  def test_check_postgre_up(self, get_postgre_status_mock, run_os_command_mock,
                            popen_mock, sleep_mock):
    from ambari_server import serverConfiguration

    p = MagicMock()
    p.communicate.return_value = (None, None)
    p.returncode = 0
    popen_mock.return_value = p
    get_postgre_status_mock.return_value = "running", 0, "", ""

    serverConfiguration.OS_TYPE = OSConst.OS_REDHAT
    p.poll.return_value = 0

    run_os_command_mock.return_value = (0, None, None)
    pg_status, retcode, out, err = PGConfig._check_postgre_up()
    self.assertEqual(0, retcode)

    serverConfiguration.OS_TYPE = OSConst.OS_SUSE
    run_os_command_mock.return_value = (0, None, None)
    p.poll.return_value = 0
    get_postgre_status_mock.return_value = "stopped", 0, "", ""
    pg_status, retcode, out, err = PGConfig._check_postgre_up()
    self.assertEqual(0, retcode)
    pass

  @patch("platform.linux_distribution")
  @patch("platform.system")
  @patch("ambari_commons.logging_utils.print_info_msg")
  @patch("ambari_commons.logging_utils.print_error_msg")
  @patch("ambari_server.serverSetup.get_ambari_properties")
  @patch("ambari_server.serverSetup.write_property")
  @patch("ambari_server.serverConfiguration.get_conf_dir")
  def test_configure_os_settings(self, get_conf_dir_mock, write_property_mock, get_ambari_properties_mock,
                                 print_error_msg_mock, print_info_msg_mock,
                                 systemMock, distMock):
    get_ambari_properties_mock.return_value = -1
    rcode = configure_os_settings()
    self.assertEqual(-1, rcode)

    p = MagicMock()
    p[OS_TYPE_PROPERTY] = 'somevalue'
    get_ambari_properties_mock.return_value = p
    rcode = configure_os_settings()
    self.assertEqual(0, rcode)

    p.__getitem__.return_value = ""
    rcode = configure_os_settings()
    self.assertEqual(0, rcode)
    self.assertTrue(write_property_mock.called)
    self.assertEqual(2, write_property_mock.call_count)
    self.assertEquals(write_property_mock.call_args_list[0][0][0], "server.os_family")
    self.assertEquals(write_property_mock.call_args_list[1][0][0], "server.os_type")
    pass


  @patch("__builtin__.open")
  @patch("ambari_server.serverConfiguration.Properties")
  @patch("ambari_server.serverConfiguration.search_file")
  @patch("ambari_server.serverConfiguration.get_conf_dir")
  def test_get_JAVA_HOME(self, get_conf_dir_mock, search_file_mock,
                         Properties_mock, openMock):
    openMock.side_effect = Exception("exception")
    result = get_JAVA_HOME()
    self.assertEqual(None, result)

    expected = os.path.dirname(__file__)
    p = MagicMock()
    p.__getitem__.return_value = expected
    openMock.side_effect = None
    Properties_mock.return_value = p
    result = get_JAVA_HOME()
    self.assertEqual(expected, result)
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  def test_prompt_db_properties_default(self):
    args = MagicMock()
    args.must_set_database_options = False

    del args.database_index
    del args.dbms
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password
    del args.persistence_type

    prompt_db_properties(args)

    self.assertEqual(args.database_index, 0)
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(LinuxDBMSConfig, "_setup_remote_server")
  @patch("ambari_server.dbConfiguration_linux.print_info_msg")
  @patch("ambari_server.dbConfiguration_linux.read_password")
  @patch("ambari_server.dbConfiguration_linux.get_validated_string_input")
  @patch("ambari_server.dbConfiguration.get_validated_string_input")
  @patch("ambari_server.serverSetup.get_YN_input")
  def test_prompt_db_properties_oracle_sname(self, gyni_mock, gvsi_mock, gvsi_2_mock, rp_mock, print_info_msg_mock, srs_mock):
    gyni_mock.return_value = True
    list_of_return_values = ["ambari-server", "ambari", "1", "1521", "localhost", "2"]

    def side_effect(*args, **kwargs):
      return list_of_return_values.pop()

    gvsi_mock.side_effect = side_effect
    gvsi_2_mock.side_effect = side_effect
    rp_mock.return_value = "password"

    args = MagicMock()
    args.must_set_database_options = True

    del args.database_index
    del args.dbms
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password
    del args.persistence_type
    del args.sid_or_sname
    del args.jdbc_url

    set_silent(False)

    prompt_db_properties(args)

    self.assertEqual(args.database_index, 1)

    props = Properties()

    factory = DBMSConfigFactory()
    dbmsConfig = factory.create(args, props)

    self.assertEqual(dbmsConfig.dbms, "oracle")
    self.assertEqual(dbmsConfig.database_port, "1521")
    self.assertEqual(dbmsConfig.database_host, "localhost")
    self.assertEqual(dbmsConfig.database_name, "ambari")
    self.assertEqual(dbmsConfig.database_username, "ambari")
    self.assertEqual(dbmsConfig.database_password, "bigdata")
    self.assertEqual(dbmsConfig.sid_or_sname, "sid")

    dbmsConfig.configure_database(props)

    self.assertEqual(dbmsConfig.database_username, "ambari-server")
    self.assertEqual(dbmsConfig.sid_or_sname, "sname")
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(LinuxDBMSConfig, "_setup_remote_server")
  @patch("ambari_server.dbConfiguration_linux.print_info_msg")
  @patch("ambari_server.dbConfiguration_linux.read_password")
  @patch("ambari_server.dbConfiguration_linux.get_validated_string_input")
  @patch("ambari_server.dbConfiguration.get_validated_string_input")
  @patch("ambari_server.serverSetup.get_YN_input")
  def test_prompt_db_properties_oracle_sid(self, gyni_mock, gvsi_mock, gvsi_2_mock, rp_mock, print_info_msg_mock, srs_mock):
    gyni_mock.return_value = True
    list_of_return_values = ["ambari-server", "ambari", "2", "1521", "localhost", "2"]

    def side_effect(*args, **kwargs):
      return list_of_return_values.pop()

    gvsi_mock.side_effect = side_effect
    gvsi_2_mock.side_effect = side_effect
    rp_mock.return_value = "password"

    args = MagicMock()
    args.must_set_database_options = True

    del args.database_index
    del args.dbms
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password
    del args.persistence_type
    del args.sid_or_sname
    del args.jdbc_url

    set_silent(False)

    prompt_db_properties(args)

    self.assertEqual(args.database_index, 1)

    props = Properties()

    factory = DBMSConfigFactory()
    dbmsConfig = factory.create(args, props)

    self.assertEqual(dbmsConfig.dbms, "oracle")
    self.assertEqual(dbmsConfig.database_port, "1521")
    self.assertEqual(dbmsConfig.database_host, "localhost")
    self.assertEqual(dbmsConfig.database_name, "ambari")
    self.assertEqual(dbmsConfig.database_username, "ambari")
    self.assertEqual(dbmsConfig.database_password, "bigdata")

    dbmsConfig.configure_database(props)

    self.assertEqual(dbmsConfig.database_username, "ambari-server")
    self.assertEqual(dbmsConfig.database_password, "password")
    self.assertEqual(dbmsConfig.sid_or_sname, "sid")
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(PGConfig, "_setup_local_server")
  @patch("ambari_server.dbConfiguration_linux.print_info_msg")
  @patch("ambari_server.dbConfiguration_linux.read_password")
  @patch("ambari_server.dbConfiguration_linux.get_validated_string_input")
  @patch("ambari_server.dbConfiguration.get_validated_string_input")
  @patch("ambari_server.serverSetup.get_YN_input")
  def test_prompt_db_properties_postgre_adv(self, gyni_mock, gvsi_mock, gvsi_2_mock, rp_mock, print_info_msg_mock, sls_mock):
    gyni_mock.return_value = True
    list_of_return_values = ["ambari-server", "ambari", "ambari", "1"]

    def side_effect(*args, **kwargs):
      return list_of_return_values.pop()

    gvsi_mock.side_effect = side_effect
    gvsi_2_mock.side_effect = side_effect
    rp_mock.return_value = "password"

    args = MagicMock()
    args.must_set_database_options = True

    del args.database_index
    del args.dbms
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password
    del args.persistence_type

    set_silent(False)

    prompt_db_properties(args)

    self.assertEqual(args.database_index, 0)

    props = Properties()

    factory = DBMSConfigFactory()
    dbmsConfig = factory.create(args, props)

    self.assertEqual(dbmsConfig.dbms, "postgres")
    self.assertEqual(dbmsConfig.database_port, "5432")
    self.assertEqual(dbmsConfig.database_host, "localhost")
    self.assertEqual(dbmsConfig.database_name, "ambari")
    self.assertEqual(dbmsConfig.database_username, "ambari")
    self.assertEqual(dbmsConfig.database_password, "bigdata")

    dbmsConfig.configure_database(props)

    self.assertEqual(dbmsConfig.database_username, "ambari-server")
    self.assertEqual(dbmsConfig.database_password, "password")
    self.assertEqual(dbmsConfig.sid_or_sname, "sid")
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_server.dbConfiguration_linux.store_password_file")
  @patch("ambari_server.dbConfiguration_linux.read_password")
  @patch("ambari_server.dbConfiguration_linux.get_validated_string_input")
  @patch("ambari_server.dbConfiguration_linux.get_YN_input")
  def test_prompt_db_properties_for_each_database_type(self, gyni_mock, gvsi_mock, rp_mock, spf_mock):
    """
    :return: Validates that installation for each database type correctly stores the database type, database name,
    and optionally the postgres schema name.
    """
    from ambari_server import serverConfiguration

    gyni_mock.return_value = True
    rp_mock.return_value = "password"
    spf_mock.return_value = "encrypted password"

    # Values to use while installing several database types
    hostname = "localhost"
    db_name = "db_ambari"
    postgres_schema = "sc_ambari"
    port = "1234"
    oracle_service = "1"
    oracle_service_name = "ambari"
    user_name = "ambari"

    # Input values
    postgres_embedded_values = [db_name, postgres_schema, hostname]
    oracle_values = [hostname, port, oracle_service, oracle_service_name, user_name]
    mysql_values = [hostname, port, db_name, user_name]
    postgres_external_values = [hostname, port, db_name, postgres_schema, user_name]
    mssql_values = [hostname, port, db_name, user_name]

    list_of_return_values = postgres_embedded_values + oracle_values + mysql_values + postgres_external_values + mssql_values
    list_of_return_values = list_of_return_values[::-1]       # Reverse the list since the input will be popped

    def side_effect(*args, **kwargs):
      return list_of_return_values.pop()
    gvsi_mock.side_effect = side_effect

    if AMBARI_CONF_VAR in os.environ:
      del os.environ[AMBARI_CONF_VAR]

    tempdir = tempfile.gettempdir()
    os.environ[AMBARI_CONF_VAR] = tempdir
    prop_file = os.path.join(tempdir, "ambari.properties")

    for i in range(0, 5):
      # Use the expected path of the ambari.properties file to delete it if it exists, and then create a new one
      # during each use case.
      if os.path.exists(prop_file):
        os.remove(prop_file)
      with open(prop_file, "w") as f:
        f.write("server.jdbc.database_name=oldDBName")
      f.close()

      serverConfiguration.AMBARI_PROPERTIES_FILE = prop_file

      args = MagicMock()
      properties = Properties()

      args.database_index = i
      args.silent = False

      del args.dbms
      del args.database_host
      del args.database_port
      del args.database_name
      del args.database_username
      del args.database_password
      del args.sid_or_sname
      del args.jdbc_url

      factory = DBMSConfigFactory()
      dbConfig = factory.create(args, properties)
      dbConfig._prompt_db_properties()

      if dbConfig._is_local_database():
        dbConfig._setup_local_server(properties)
      else:
        dbConfig._setup_remote_server(properties)

      if i == 0:
        # Postgres Embedded
        self.assertEqual(properties[JDBC_DATABASE_PROPERTY], "postgres")
        self.assertEqual(properties[JDBC_DATABASE_NAME_PROPERTY], db_name)
        self.assertEqual(properties[JDBC_POSTGRES_SCHEMA_PROPERTY], postgres_schema)
        self.assertEqual(properties[PERSISTENCE_TYPE_PROPERTY], "local")
      elif i == 1:
        # Oracle
        self.assertEqual(properties[JDBC_DATABASE_PROPERTY], "oracle")
        self.assertFalse(JDBC_POSTGRES_SCHEMA_PROPERTY in properties.propertyNames())
        self.assertEqual(properties[PERSISTENCE_TYPE_PROPERTY], "remote")
      elif i == 2:
        # MySQL
        self.assertEqual(properties[JDBC_DATABASE_PROPERTY], "mysql")
        self.assertFalse(JDBC_POSTGRES_SCHEMA_PROPERTY in properties.propertyNames())
        self.assertEqual(properties[PERSISTENCE_TYPE_PROPERTY], "remote")
      elif i == 3:
        # Postgres External
        self.assertEqual(properties[JDBC_DATABASE_PROPERTY], "postgres")
        self.assertEqual(properties[JDBC_DATABASE_NAME_PROPERTY], db_name)
        self.assertEqual(properties[JDBC_POSTGRES_SCHEMA_PROPERTY], postgres_schema)
        self.assertEqual(properties[PERSISTENCE_TYPE_PROPERTY], "remote")
      elif i == 4:
        # MSSQL
        self.assertEqual(properties[JDBC_DATABASE_PROPERTY], "mssql")
        self.assertFalse(JDBC_POSTGRES_SCHEMA_PROPERTY in properties.propertyNames())
        self.assertEqual(properties[PERSISTENCE_TYPE_PROPERTY], "remote")
    pass

  @patch.object(os.path, "exists")
  @patch.object(os.path, "isfile")
  def test_validate_jdk(self, isfile_mock, exists_mock):
    exists_mock.side_effect = [False]
    result = validate_jdk("path")
    self.assertFalse(result)

    exists_mock.side_effect = [True, False]
    result = validate_jdk("path")
    self.assertFalse(result)

    exists_mock.side_effect = [True, True]
    isfile_mock.return_value = False
    result = validate_jdk("path")
    self.assertFalse(result)

    exists_mock.side_effect = [True, True]
    isfile_mock.return_value = True
    result = validate_jdk("path")
    self.assertTrue(result)
    pass

  @patch("glob.glob")
  @patch("ambari_server.serverConfiguration.get_JAVA_HOME")
  @patch("ambari_server.serverConfiguration.validate_jdk")
  def test_find_jdk(self, validate_jdk_mock, get_JAVA_HOME_mock, globMock):
    get_JAVA_HOME_mock.return_value = "somewhere"
    validate_jdk_mock.return_value = True
    result = find_jdk()
    self.assertEqual("somewhere", result)

    get_JAVA_HOME_mock.return_value = None
    globMock.return_value = []
    result = find_jdk()
    self.assertEqual(None, result)

    globMock.return_value = ["one", "two"]
    result = find_jdk()
    self.assertNotEqual(None, result)

    globMock.return_value = ["one", "two"]
    validate_jdk_mock.side_effect = [False, True]
    result = find_jdk()
    self.assertEqual(result, "one")
    pass


  @patch("os.path.exists")
  @patch("zipfile.ZipFile")
  @patch("os.path.split")
  @patch("os.listdir")
  @patch("ambari_server.serverSetup.copy_files")
  @patch("shutil.rmtree")
  def test_unpack_jce_policy(self, rmtree_mock, copy_files_mock, os_listdir_mock, os_path_split_mock, zipfile_mock, exists_mock):

    # Testing the case when the zip file doesn't contains any folder
    exists_mock.return_value = True
    zipfile = MagicMock()
    zipfile_mock.return_value = zipfile
    zip_members = ["US_export_policy.jar", "local_policy.jar", "README.txt"]
    zipfile.namelist.return_value = zip_members
    os_path_split_mock.return_value = [""]

    expand_jce_zip_file("", "")
    self.assertTrue(exists_mock.called)
    self.assertTrue(zipfile_mock.called)
    self.assertTrue(os_path_split_mock.called)

    # Testing the case when the zip file contains a folder
    unziped_jce_path = "jce"
    os_path_split_mock.return_value = unziped_jce_path

    expand_jce_zip_file("", "")
    self.assertTrue(exists_mock.called)
    self.assertTrue(zipfile_mock.called)
    self.assertTrue(os_listdir_mock.called)
    self.assertTrue(copy_files_mock.called)
    self.assertTrue(rmtree_mock.called)

    # Testing when the jdk_security_path or jce_zip_path doesn't exist
    exists_mock.return_value = False
    try:
      expand_jce_zip_file("", "")
    except FatalException:
      self.assertTrue(True)
    exists_mock.return_value = True

    # Testing when zipfile fail with an error
    zipfile_mock.side_effect = FatalException(1,"Extract error")
    try:
      expand_jce_zip_file("", "")
    except FatalException:
      self.assertTrue(True)


  @patch("os.path.exists")
  @patch("shutil.copy")
  @patch("os.path.split")
  @patch("ambari_server.serverSetup.update_properties")
  @patch.object(JDKSetup, "unpack_jce_policy")
  @patch("ambari_server.serverSetup.get_ambari_properties")
  @patch("ambari_commons.os_utils.search_file")
  @patch("__builtin__.open")
  def test_setup_jce_policy(self, open_mock, search_file_mock, get_ambari_properties_mock, unpack_jce_policy_mock,
                            update_properties_mock, path_split_mock, shutil_copy_mock, exists_mock):
    exists_mock.return_value = True
    properties = Properties()
    properties.process_pair(JAVA_HOME_PROPERTY, "/java_home")
    unpack_jce_policy_mock.return_value = 0
    get_ambari_properties_mock.return_value = properties
    conf_file = 'etc/ambari-server/conf/ambari.properties'
    search_file_mock.return_value = conf_file
    path_split_mock.return_value = ["/path/to", "JCEPolicy.zip"]
    args = ['setup-jce', '/path/to/JCEPolicy.zip']

    setup_jce_policy(args)
    shutil_copy_mock.assert_called_with(args[1], configDefaults.SERVER_RESOURCES_DIR)
    self.assertTrue(unpack_jce_policy_mock.called)
    self.assertTrue(get_ambari_properties_mock.called)
    self.assertTrue(update_properties_mock.called)

    # Testing that if the source and the destination is the same will not try to copy the file
    path_split_mock.return_value = [configDefaults.SERVER_RESOURCES_DIR, "JCEPolicy.zip"]
    shutil_copy_mock.reset_mock()

    setup_jce_policy(args)
    self.assertFalse(shutil_copy_mock.called)
    self.assertTrue(unpack_jce_policy_mock.called)
    self.assertTrue(get_ambari_properties_mock.called)
    self.assertTrue(update_properties_mock.called)
    path_split_mock.return_value = ["/path/to", "JCEPolicy.zip"]

    # Testing with bad path
    exists_mock.return_value = False
    try:
      setup_jce_policy(args)
    except FatalException:
      self.assertTrue(True)
    exists_mock.return_value = True

    # Testing with an error produced by shutil.copy
    shutil_copy_mock.reset_mock()
    shutil_copy_mock.side_effect = FatalException(1, "Error trying to copy the file.")
    try:
      setup_jce_policy(args)
    except FatalException:
      self.assertTrue(True)

    # Testing with an error produced by Properties.store function
    update_properties_mock.side_effect = Exception("Invalid file.")
    try:
      setup_jce_policy(args)
    except Exception:
      self.assertTrue(True)
    update_properties_mock.reset_mock()

    # Testing with an error produced by unpack_jce_policy
    unpack_jce_policy_mock.side_effect = FatalException(1, "Can not install JCE policy")
    try:
      setup_jce_policy(args)
    except FatalException:
      self.assertTrue(True)
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_commons.firewall.run_os_command")
  @patch("os.path.exists")
  @patch("os.path.isfile")
  @patch("ambari_commons.os_utils.remove_file")
  @patch("ambari_server.dbConfiguration_linux.LinuxDBMSConfig.ensure_jdbc_driver_installed")
  @patch("ambari_server.dbConfiguration_linux.get_YN_input")
  @patch("ambari_server.serverSetup.update_properties")
  @patch("ambari_server.dbConfiguration_linux.get_ambari_properties")
  @patch("ambari_server.dbConfiguration_linux.store_password_file")
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  @patch("ambari_server.dbConfiguration_linux.PGConfig._configure_postgres")
  @patch("ambari_server.dbConfiguration_linux.PGConfig._check_postgre_up")
  @patch("ambari_server.dbConfiguration_linux.PGConfig._is_jdbc_user_changed")
  @patch("ambari_server.serverSetup.verify_setup_allowed")
  @patch("ambari_server.dbConfiguration_linux.read_password")
  @patch("ambari_server.dbConfiguration_linux.get_validated_string_input")
  @patch("ambari_server.dbConfiguration.get_validated_string_input")
  @patch("ambari_server.serverSetup.get_YN_input")
  @patch("ambari_server.serverSetup.get_ambari_properties")
  @patch("ambari_server.serverSetup.configure_os_settings")
  @patch("ambari_server.serverSetup.download_and_install_jdk")
  @patch("ambari_server.serverSetup.check_ambari_user")
  @patch("ambari_server.serverSetup.check_jdbc_drivers")
  @patch("ambari_server.serverSetup.disable_security_enhancements")
  @patch("ambari_server.serverSetup.is_root")
  @patch("ambari_server.serverSetup.proceedJDBCProperties")
  @patch("ambari_server.serverSetup.extract_views")
  @patch("ambari_server.serverSetup.adjust_directory_permissions")
  @patch("ambari_server.serverSetup.service_setup")
  @patch("ambari_server.serverSetup.read_ambari_user")
  @patch("ambari_server.serverSetup.expand_jce_zip_file")
  def test_setup(self, expand_jce_zip_file_mock, read_ambari_user_mock,
                 service_setup_mock, adjust_dirs_mock, extract_views_mock, proceedJDBCProperties_mock, is_root_mock,
                 disable_security_enhancements_mock, check_jdbc_drivers_mock, check_ambari_user_mock,
                 download_jdk_mock, configure_os_settings_mock, get_ambari_properties_mock,
                 get_YN_input_mock, gvsi_mock, gvsi_1_mock,
                 read_password_mock, verify_setup_allowed_method, is_jdbc_user_changed_mock, check_postgre_up_mock,
                 configure_postgres_mock, run_os_command_1_mock,
                 store_password_file_mock, get_ambari_properties_1_mock, update_properties_mock,
                 get_YN_input_1_mock, ensure_jdbc_driver_installed_mock,
                 remove_file_mock, isfile_mock, exists_mock,
                 run_os_command_mock):
    hostname = "localhost"
    db_name = "db_ambari"
    postgres_schema = "sc_ambari"
    port = "1234"
    oracle_service = "1"
    oracle_service_name = "ambari"
    user_name = "ambari"

    args = MagicMock()

    del args.dbms
    del args.database_index
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password

    args.silent = False

    failed = False
    properties = Properties()

    get_YN_input_mock.return_value = False
    isfile_mock.return_value = False
    verify_setup_allowed_method.return_value = 0
    exists_mock.return_value = False
    remove_file_mock.return_value = 0
    run_os_command_mock.return_value = 3,"",""
    extract_views_mock.return_value = 0
    read_ambari_user_mock.return_value = "ambari"
    read_password_mock.return_value = "bigdata2"
    get_ambari_properties_mock.return_value = properties
    get_ambari_properties_1_mock.return_value = properties
    store_password_file_mock.return_value = "encrypted_bigdata2"
    ensure_jdbc_driver_installed_mock.return_value = True
    check_postgre_up_mock.return_value = (PGConfig.PG_STATUS_RUNNING, 0, "", "")
    configure_postgres_mock.return_value = (0, "", "")
    run_os_command_1_mock.return_value = (0, "", "")
    expand_jce_zip_file_mock.return_value = 0

    def reset_mocks():
      is_jdbc_user_changed_mock.reset_mock()
      is_root_mock.reset_mock()
      disable_security_enhancements_mock.reset_mock()
      check_jdbc_drivers_mock.reset_mock()
      check_ambari_user_mock.reset_mock()
      run_os_command_mock.reset_mock()
      configure_os_settings_mock.reset_mock()
      run_os_command_1_mock.reset_mock()
      get_YN_input_1_mock.reset_mock()
      update_properties_mock.reset_mock()

      args = MagicMock()

      del args.dbms
      del args.database_index
      del args.database_host
      del args.database_port
      del args.database_name
      del args.database_username
      del args.database_password
      del args.persistence_type
      del args.sid_or_sname
      del args.jdbc_url

      args.jdbc_driver= None
      args.jdbc_db = None

      args.silent = False

      return args


    # Testing call under non-root
    is_root_mock.return_value = False
    try:
      setup(args)
      self.fail("Should throw exception")
    except FatalException as fe:
      # Expected
      self.assertTrue("root-level" in fe.reason)
      pass

    args = reset_mocks()

    # Testing calls under root
    # remote case
    is_root_mock.return_value = True
    disable_security_enhancements_mock.return_value = (0, "")
    check_ambari_user_mock.return_value = (0, False, 'user', None)
    check_jdbc_drivers_mock.return_value = 0
    download_jdk_mock.return_value = 0
    configure_os_settings_mock.return_value = 0

    result = setup(args)

    self.assertEqual(None, result)
    self.assertTrue(check_ambari_user_mock.called)
    self.assertEqual(1, run_os_command_mock.call_count)

    #Local case
    args = reset_mocks()

    # Input values
    db_selection_values = ["1"]
    postgres_values = [db_name, postgres_schema, hostname]

    postgres_values = postgres_values[::-1]       # Reverse the list since the input will be popped

    def side_effect(*args, **kwargs):
      return db_selection_values.pop()
    gvsi_mock.side_effect = side_effect

    def side_effect_1(*args, **kwargs):
      return postgres_values.pop()
    gvsi_1_mock.side_effect = side_effect_1

    get_YN_input_mock.return_value = True
    # is_local_database_mock.return_value = True
    is_jdbc_user_changed_mock.return_value = False

    try:
      result = setup(args)
    except FatalException:
      self.fail("Setup should be successful")
    self.assertEqual(None, result)
    self.assertTrue(is_jdbc_user_changed_mock.called)
    self.assertTrue(update_properties_mock.called)
    self.assertTrue(run_os_command_1_mock.called)
    self.assertFalse(remove_file_mock.called)

    self.assertTrue("Ambari-DDL-Postgres-EMBEDDED-CREATE.sql" in run_os_command_1_mock.call_args[0][0][3])

    #if DB user name was changed
    args = reset_mocks()

    # is_local_database_mock.return_value = True
    is_jdbc_user_changed_mock.return_value = True

    db_selection_values = ["1"]
    postgres_values = [db_name, postgres_schema, hostname]

    postgres_values = postgres_values[::-1]       # Reverse the list since the input will be popped

    try:
      result = setup(args)
    except FatalException:
      self.fail("Setup should be successful")
    self.assertEqual(None, result)
    self.assertTrue(is_jdbc_user_changed_mock.called)
    self.assertTrue(update_properties_mock.called)
    self.assertTrue(run_os_command_1_mock.called)
    self.assertFalse(remove_file_mock.called)

    #negative case
    args = reset_mocks()

    # Use remote database
    get_YN_input_1_mock.return_value = False
    db_selection_values = ["4"]
    postgres_values = [hostname, port, db_name, postgres_schema, user_name]

    postgres_values = postgres_values[::-1]       # Reverse the list since the input will be popped

    try:
      result = setup(args)
      self.fail("Should throw exception")
    except NonFatalException as fe:
      self.assertTrue("Remote database setup aborted." in fe.reason)

    self.assertFalse(run_os_command_1_mock.called)

    # test not run setup if ambari-server setup executed with jdbc properties
    args = reset_mocks()
    # is_server_runing_mock.return_value = (False, 1)
    args.jdbc_driver= "path/to/driver"
    args.jdbc_db = "test_db_name"


    setup(args)
    self.assertTrue(proceedJDBCProperties_mock.called)
    self.assertFalse(disable_security_enhancements_mock.called)
    self.assertFalse(check_ambari_user_mock.called)
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(OracleConfig, "_get_remote_script_line")
  @patch("ambari_server.serverSetup.is_server_runing")
  @patch("ambari_server.dbConfiguration_linux.get_YN_input")
  @patch("ambari_server.serverSetup.get_YN_input")
  @patch.object(PGConfig, "_setup_db")
  @patch("ambari_server.dbConfiguration_linux.print_warning_msg")
  @patch("ambari_server.dbConfiguration_linux.print_info_msg")
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  @patch("ambari_server.dbConfiguration.decrypt_password_for_alias")
  @patch("ambari_server.serverSetup.get_ambari_properties")
  @patch("ambari_server.serverSetup.is_root")
  def test_reset(self, is_root_mock, get_ambari_properties_mock, decrypt_password_for_alias_mock,
                 run_os_command_mock, print_info_msg_mock, print_warning_msg_mock,
                 setup_db_mock, get_YN_input_mock, get_YN_input_2_mock, is_server_running_mock,
                 get_remote_script_line_mock):
    def reset_mocks():
      args = MagicMock()
      del args.dbms
      del args.database_index
      del args.database_host
      del args.database_port
      del args.database_name
      del args.database_username
      del args.database_password
      del args.persistence_type
      del args.init_script_file
      del args.drop_script_file
      del args.sid_or_sname
      del args.jdbc_url
      return args

    properties = Properties()

    get_ambari_properties_mock.return_value = properties

    args = reset_mocks()
    args.persistence_type = "local"

    get_YN_input_mock.return_value = False
    decrypt_password_for_alias_mock.return_value = "password"
    is_server_running_mock.return_value = (False, 0)
    setup_db_mock.side_effect = [(0,None, None),(0,None, "ERROR: database 'ambari' is being accessed by other users"), (0, None, "ERROR: user 'mapred' already exist")]

    # Testing call under non-root
    is_root_mock.return_value = False
    try:
      reset(args)
      self.fail("Should throw exception")
    except FatalException as fe:
      # Expected
      self.assertTrue("root-level" in fe.reason)
      pass

    # Testing calls under root
    is_root_mock.return_value = True
    try:
      reset(args)
      self.fail("Should throw exception")
    except FatalException as fe:
      # Expected
      self.assertFalse("root-level" in fe.reason)
      pass

    get_YN_input_mock.return_value = True
    get_YN_input_2_mock.return_value = True
    run_os_command_mock.return_value = (1, None, None)
    try:
      reset(args)
      self.fail("Should throw exception")
    except FatalException:
      # Expected
      pass

    run_os_command_mock.return_value = (0, None, None)
    reset(args)
    self.assertTrue(setup_db_mock.called)

    # Database errors cases
    is_server_running_mock.side_effect = [(True, 123), (False, 0), (False, 0), (False, 0), (False, 0)]

    try:
      reset(args)
      self.fail("Should throw exception")
    except FatalException:
      # Expected
      pass

    try:
      reset(args)
      self.fail("Should throw exception")
    except NonFatalException:
      # Expected
      pass

    args = reset_mocks()
    args.dbms = "postgres"

    #get_remote_script_line_mock.return_value = None
    try:
      #remote db case
      reset(args)
      self.fail("Should throw exception")
    except NonFatalException:
      # Expected
      pass

    args = reset_mocks()
    args.dbms = "oracle"

    print_warning_msg_mock.reset_mock()
    get_remote_script_line_mock.reset_mock()
    get_remote_script_line_mock.side_effect = ["drop", "create"]
    try:
      #remote db case (not Postgres)
      rcode = reset(args)
      self.fail("Should throw exception")
    except NonFatalException:
      # Expected
      self.assertTrue(get_remote_script_line_mock.called)
      self.assertTrue(print_warning_msg_mock.called)
      pass
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_server.serverSetup.get_YN_input")
  @patch("__builtin__.raw_input")
  @patch("ambari_server.serverSetup.is_root")
  def test_reset_default(self, is_root_mock, raw_input_mock, get_YN_inputMock):
    is_root_mock.return_value=True
    get_YN_inputMock.return_value = False
    raw_input_mock.return_value=""
    args = MagicMock()

    try:
      reset(args)
      self.fail("Should throw exception")
    except FatalException as fe:
      # Expected
      self.assertTrue(fe.code == 1)
      pass

    pass


  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(PGConfig, "_setup_db")
  @patch("ambari_server.dbConfiguration_linux.print_info_msg")
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  #@patch("ambari_server.serverSetup.parse_properties_file")
  @patch("ambari_server.serverSetup.is_root")
  #@patch("ambari_server.serverSetup.check_database_name_property")
  @patch("ambari_server.serverSetup.is_server_runing")
  def test_silent_reset(self, is_server_runing_mock, #check_database_name_property_mock,
                        is_root_mock, #parse_properties_file_mock,
                        run_os_command_mock, print_info_msg_mock,
                        setup_db_mock):
    is_root_mock.return_value = True

    args = MagicMock()

    del args.dbms
    del args.database_index
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password
    del args.persistence_type

    set_silent(True)

    self.assertTrue(get_silent())
    setup_db_mock.return_value = (0, None, None)
    run_os_command_mock.return_value = (0, None, None)
    is_server_runing_mock.return_value = (False, 0)

    def signal_handler(signum, frame):
      self.fail("Timed out!")

    signal.signal(signal.SIGALRM, signal_handler)

    try:
      signal.alarm(5)
      rcode = reset(args)
      signal.alarm(0)
      self.assertEqual(None, rcode)
      self.assertTrue(setup_db_mock.called)
    finally:
      signal.signal(signal.SIGALRM, signal.SIG_IGN)
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("sys.stdout.flush")
  @patch("sys.stdout.write")
  @patch("ambari_server_main.looking_for_pid")
  @patch("ambari_server_main.wait_for_pid")
  @patch("ambari_server_main.save_main_pid_ex")
  @patch("ambari_server_main.check_exitcode")
  @patch("os.makedirs")
  @patch("ambari_server_main.locate_file")
  @patch.object(_ambari_server_, "is_server_runing")
  @patch("os.chown")
  @patch("ambari_server.setupSecurity.get_master_key_location")
  @patch("ambari_server_main.save_master_key")
  @patch("ambari_server_main.get_is_persisted")
  @patch("ambari_server_main.get_is_secure")
  @patch('os.chmod', autospec=True)
  @patch("ambari_server.serverConfiguration.write_property")
  @patch("ambari_server.serverConfiguration.get_validated_string_input")
  @patch("os.environ")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.serverSetup.get_ambari_properties")
  @patch("ambari_server.serverConfiguration.get_ambari_properties")
  @patch("ambari_server_main.get_ambari_properties")
  @patch("os.path.exists")
  @patch("__builtin__.open")
  @patch("subprocess.Popen")
  @patch("ambari_server.serverConfiguration.search_file")
  @patch("ambari_server_main.check_database_name_property")
  @patch("ambari_server_main.find_jdk")
  @patch("ambari_server_main.print_warning_msg")
  @patch("ambari_server_main.print_info_msg")
  @patch.object(PGConfig, "_check_postgre_up")
  @patch("ambari_server_main.read_ambari_user")
  @patch("ambari_server.dbConfiguration_linux.is_root")
  @patch("ambari_server_main.is_root")
  @patch.object(LinuxDBMSConfig, "_find_jdbc_driver")
  @patch("getpass.getuser")
  @patch("os.chdir")
  @patch.object(ResourceFilesKeeper, "perform_housekeeping")
  def test_start(self, perform_housekeeping_mock, chdir_mock, getuser_mock, find_jdbc_driver_mock,
                 is_root_mock, is_root_2_mock, read_ambari_user_mock,
                 check_postgre_up_mock, print_info_msg_mock, print_warning_msg_mock,
                 find_jdk_mock, check_database_name_property_mock, search_file_mock,
                 popenMock, openMock, pexistsMock,
                 get_ambari_properties_mock, get_ambari_properties_2_mock, get_ambari_properties_3_mock,
                 get_ambari_properties_4_mock, os_environ_mock,
                 get_validated_string_input_method, write_property_method,
                 os_chmod_method, get_is_secure_mock, get_is_persisted_mock,
                 save_master_key_method, get_master_key_location_method,
                 os_chown_mock, is_server_running_mock, locate_file_mock,
                 os_makedirs_mock, check_exitcode_mock, save_main_pid_ex_mock,
                 wait_for_pid_mock, looking_for_pid_mock, stdout_write_mock, stdout_flush_mock):

    def reset_mocks():
      pexistsMock.reset_mock()

      args = MagicMock()
      del args.dbms
      del args.database_index
      del args.database_host
      del args.database_port
      del args.database_name
      del args.database_username
      del args.database_password
      del args.persistence_type
      del args.sid_or_sname
      del args.jdbc_url
      del args.debug
      del args.suspend_start

      return args

    args = reset_mocks()

    locate_file_mock.side_effect = lambda *args: '/bin/su' if args[0] == 'su' else '/bin/sh'
    f = MagicMock()
    f.readline.return_value = '42'
    openMock.return_value = f

    looking_for_pid_mock.return_value = [{
        "pid": "777",
        "exe": "/test",
        "cmd": "test arg"
    }]
    wait_for_pid_mock.return_value = 1
    check_exitcode_mock.return_value = 0

    p = Properties()
    p.process_pair(SECURITY_IS_ENCRYPTION_ENABLED, 'False')

    get_ambari_properties_4_mock.return_value = \
      get_ambari_properties_3_mock.return_value = get_ambari_properties_2_mock.return_value = \
      get_ambari_properties_mock.return_value = p
    get_is_secure_mock.return_value = False
    get_is_persisted_mock.return_value = (False, None)
    search_file_mock.return_value = None
    is_server_running_mock.return_value = (True, 123)
    os_chown_mock.return_value = None
    # Checking "server is running"
    pexistsMock.return_value = True
    if get_platform() != PLATFORM_WINDOWS:
      with patch("pwd.getpwnam") as getpwnam_mock:
        pw = MagicMock()
        pw.setattr('pw_uid', 0)
        pw.setattr('pw_gid', 0)
        getpwnam_mock.return_value = pw

    try:
      _ambari_server_.start(args)
      self.fail("Should fail with 'Server is running'")
    except FatalException as e:
      # Expected
      self.assertTrue('Ambari Server is already running.' in e.reason)

    args = reset_mocks()

    is_server_running_mock.return_value = (False, 0)
    pexistsMock.return_value = False

    # Checking situation when ambari user is not set up
    read_ambari_user_mock.return_value = None
    try:
      _ambari_server_.start(args)
      self.fail("Should fail with 'Can not detect a system user for Ambari'")
    except FatalException as e:
      # Expected
      self.assertTrue('Unable to detect a system user for Ambari Server.' in e.reason)

    # Checking start from non-root when current user is not the same as a
    # custom user
    args = reset_mocks()
    read_ambari_user_mock.return_value = "dummy-user"
    getuser_mock.return_value = "non_custom_user"
    is_root_2_mock.return_value = is_root_mock.return_value = False
    try:
      _ambari_server_.start(args)
      self.fail("Should fail with 'Can not start ambari-server as user...'")
    except FatalException as e:
      # Expected
      self.assertTrue('Unable to start Ambari Server as user' in e.reason)
      #self.assertFalse(parse_properties_file_mock.called)

    # Checking "jdk not found"
    args = reset_mocks()
    is_root_2_mock.return_value = is_root_mock.return_value = True
    find_jdk_mock.return_value = None

    try:
      _ambari_server_.start(args)
      self.fail("Should fail with 'No JDK found'")
    except FatalException as e:
      # Expected
      self.assertTrue('No JDK found' in e.reason)

    args = reset_mocks()
    find_jdk_mock.return_value = "somewhere"

    ## Testing workflow under root
    is_root_2_mock.return_value = is_root_mock.return_value = True

    # Remote DB
    p.process_pair(JDBC_DATABASE_PROPERTY, 'oracle')
    p.process_pair(PERSISTENCE_TYPE_PROPERTY, 'remote')

    # Case when jdbc driver is not used
    find_jdbc_driver_mock.return_value = -1
    try:
      _ambari_server_.start(args)
      self.fail("Should fail with exception")
    except FatalException as e:
      self.assertTrue('Before starting Ambari Server' in e.reason)

    args = reset_mocks()

    # Remote DB
    p.process_pair(JDBC_DATABASE_PROPERTY, 'oracle')
    p.process_pair(PERSISTENCE_TYPE_PROPERTY, 'remote')

    find_jdbc_driver_mock.reset_mock()
    find_jdbc_driver_mock.return_value = -1
    try:
      _ambari_server_.start(args)
    except FatalException as e:
      # Ignored
      pass

    args = reset_mocks()

    # Remote DB
    p.process_pair(JDBC_DATABASE_PROPERTY, 'oracle')
    p.process_pair(PERSISTENCE_TYPE_PROPERTY, 'remote')

    find_jdbc_driver_mock.reset_mock()
    find_jdbc_driver_mock.return_value = 0

    # Test exception handling on resource files housekeeping
    perform_housekeeping_mock.reset_mock()
    perform_housekeeping_mock.side_effect = KeeperException("some_reason")

    pexistsMock.return_value = True

    try:
      _ambari_server_.start(args)
      self.fail("Should fail with exception")
    except FatalException as e:
      self.assertTrue('some_reason' in e.reason)
    self.assertTrue(perform_housekeeping_mock.called)

    perform_housekeeping_mock.side_effect = lambda *v, **kv : None
    perform_housekeeping_mock.reset_mock()

    self.assertFalse('Unable to start PostgreSQL server' in e.reason)
    self.assertFalse(check_postgre_up_mock.called)

    args = reset_mocks()

    # Local DB
    p.process_pair(JDBC_DATABASE_PROPERTY, 'postgres')
    p.process_pair(PERSISTENCE_TYPE_PROPERTY, 'local')

    check_postgre_up_mock.reset_mock()

    # case: postgres failed to start
    check_postgre_up_mock.return_value = None, 1, "Unable to start PostgreSQL serv", "error"
    try:
      _ambari_server_.start(args)
      self.fail("Should fail with 'Unable to start PostgreSQL server'")
    except FatalException as e:
      # Expected
      self.assertTrue('Unable to start PostgreSQL server' in e.reason)
      self.assertTrue(check_postgre_up_mock.called)

    args = reset_mocks()

    # Local DB
    p.process_pair(JDBC_DATABASE_PROPERTY, 'postgres')
    p.process_pair(PERSISTENCE_TYPE_PROPERTY, 'local')

    check_postgre_up_mock.return_value = "running", 0, "success", ""

    # Case: custom user is "root"
    read_ambari_user_mock.return_value = "root"

    # Java failed to start
    proc = MagicMock()
    proc.pid = -186
    popenMock.return_value = proc

    try:
      _ambari_server_.start(args)
    except FatalException as e:
      # Expected
      self.assertTrue(popenMock.called)
      self.assertTrue('Ambari Server java process died' in e.reason)
      self.assertTrue(perform_housekeeping_mock.called)

    args = reset_mocks()

    # Java OK
    proc.pid = 186
    popenMock.reset_mock()

    _ambari_server_.start(args)
    self.assertTrue(popenMock.called)
    popen_arg = popenMock.call_args[0][0]
    self.assertTrue(popen_arg[0] == "/bin/sh")
    self.assertTrue(perform_housekeeping_mock.called)

    args = reset_mocks()

    # Local DB
    p.process_pair(JDBC_DATABASE_PROPERTY, 'postgres')
    p.process_pair(PERSISTENCE_TYPE_PROPERTY, 'local')

    perform_housekeeping_mock.reset_mock()
    popenMock.reset_mock()

    # Case: custom user is  not "root"
    read_ambari_user_mock.return_value = "not-root-user"
    _ambari_server_.start(args)
    self.assertTrue(chdir_mock.called)
    self.assertTrue(popenMock.called)
    popen_arg = popenMock.call_args_list[0][0][0]
    self.assertTrue("; /bin/su" in popen_arg[2])
    self.assertTrue(perform_housekeeping_mock.called)

    args = reset_mocks()

    # Local DB
    p.process_pair(JDBC_DATABASE_PROPERTY, 'postgres')
    p.process_pair(PERSISTENCE_TYPE_PROPERTY, 'local')

    check_postgre_up_mock.reset_mock()
    popenMock.reset_mock()

    ## Testing workflow under non-root
    is_root_2_mock.return_value = is_root_mock.return_value = False
    read_ambari_user_mock.return_value = "not-root-user"
    getuser_mock.return_value = read_ambari_user_mock.return_value

    _ambari_server_.start(args)

    self.assertFalse(check_postgre_up_mock.called)

    args = reset_mocks()

    # Remote DB
    p.process_pair(JDBC_DATABASE_PROPERTY, 'postgres')
    p.process_pair(PERSISTENCE_TYPE_PROPERTY, 'remote')

    _ambari_server_.start(args)

    self.assertFalse(check_postgre_up_mock.called)

    args = reset_mocks()

    # Remote DB
    p.process_pair(JDBC_DATABASE_PROPERTY, 'postgres')
    p.process_pair(PERSISTENCE_TYPE_PROPERTY, 'remote')

    # Checking call
    _ambari_server_.start(args)
    self.assertTrue(popenMock.called)
    popen_arg = popenMock.call_args[0][0]
    self.assertTrue(popen_arg[0] == "/bin/sh")

    args = reset_mocks()

    # Remote DB
    p.process_pair(JDBC_DATABASE_PROPERTY, 'postgres')
    p.process_pair(PERSISTENCE_TYPE_PROPERTY, 'remote')

    # Test start under wrong user
    read_ambari_user_mock.return_value = "not-root-user"
    getuser_mock.return_value = "non_custom_user"
    try:
      _ambari_server_.start(args)
      self.fail("Can not start ambari-server as user non_custom_user.")
    except FatalException as e:
      # Expected
      self.assertTrue('Unable to start Ambari Server as user' in e.reason)

    args = reset_mocks()

    # Check environ master key is set
    popenMock.reset_mock()
    os_environ_mock.copy.return_value = {"a": "b",
                                        SECURITY_KEY_ENV_VAR_NAME: "masterkey"}
    p.process_pair(JDBC_DATABASE_PROPERTY, 'postgres')
    p.process_pair(PERSISTENCE_TYPE_PROPERTY, 'local')
    read_ambari_user_mock.return_value = "root"
    is_root_2_mock.return_value = is_root_mock.return_value = True

    _ambari_server_.start(args)

    self.assertFalse(get_validated_string_input_method.called)
    self.assertFalse(save_master_key_method.called)
    popen_arg = popenMock.call_args[1]['env']
    self.assertEquals(os_environ_mock.copy.return_value, popen_arg)

    args = reset_mocks()

    # Check environ master key is not set
    popenMock.reset_mock()
    os_environ_mock.reset_mock()
    p.process_pair(SECURITY_IS_ENCRYPTION_ENABLED, 'True')
    os_environ_mock.copy.return_value = {"a": "b"}
    p.process_pair(JDBC_DATABASE_PROPERTY, 'postgres')
    p.process_pair(PERSISTENCE_TYPE_PROPERTY, 'local')
    read_ambari_user_mock.return_value = "root"
    is_root_2_mock.return_value = is_root_mock.return_value = True
    get_validated_string_input_method.return_value = "masterkey"
    os_chmod_method.return_value = None
    get_is_secure_mock.return_value = True

    _ambari_server_.start(args)

    self.assertTrue(get_validated_string_input_method.called)
    self.assertTrue(save_master_key_method.called)
    popen_arg = popenMock.call_args[1]['env']
    self.assertEquals(os_environ_mock.copy.return_value, popen_arg)
    pass


  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(_ambari_server_, "is_server_runing")
  @patch("os.remove")
  @patch("os.killpg")
  @patch("os.getpgid")
  @patch.object(_ambari_server_, "print_info_msg")
  def test_stop(self, print_info_msg_mock, gpidMock, removeMock,
                killMock, isServerRuningMock):
    isServerRuningMock.return_value = (True, 123)

    _ambari_server_.stop(None)

    self.assertTrue(killMock.called)
    self.assertTrue(removeMock.called)
    pass

  @patch.object(_ambari_server_, "BackupRestore_main")
  def test_backup(self, bkrestore_mock):
    args = ["", "/some/path/file.zip"]
    _ambari_server_.backup(args)
    self.assertTrue(bkrestore_mock.called)
    pass

  @patch.object(_ambari_server_, "BackupRestore_main")
  def test_backup_no_path(self, bkrestore_mock):
    args = [""]
    _ambari_server_.backup(args)
    self.assertTrue(bkrestore_mock.called)
    pass

  @patch.object(_ambari_server_, "BackupRestore_main")
  def test_restore(self, bkrestore_mock):
    args = ["", "/some/path/file.zip"]
    _ambari_server_.restore(args)
    self.assertTrue(bkrestore_mock.called)
    pass

  @patch.object(_ambari_server_, "BackupRestore_main")
  def test_restore_no_path(self, bkrestore_mock):
    args = [""]
    _ambari_server_.restore(args)
    self.assertTrue(bkrestore_mock.called)
    pass

  @patch("ambari_server.serverUpgrade.is_root")
  @patch("ambari_server.serverUpgrade.check_database_name_property")
  @patch("ambari_server.serverUpgrade.run_stack_upgrade")
  def test_upgrade_stack(self, run_stack_upgrade_mock,
                         check_database_name_property_mock, is_root_mock):
    # Testing call under non-root
    is_root_mock.return_value = False

    args = ['', 'HDP-2.0']
    try:
      upgrade_stack(args)
      self.fail("Should throw exception")
    except FatalException as fe:
      # Expected
      self.assertTrue("root-level" in fe.reason)
      pass

    # Testing calls under root
    is_root_mock.return_value = True
    run_stack_upgrade_mock.return_value = 0
    upgrade_stack(args)

    self.assertTrue(run_stack_upgrade_mock.called)
    run_stack_upgrade_mock.assert_called_with("HDP", "2.0", None, None)
    pass

  @patch("ambari_server.serverUpgrade.get_ambari_properties")
  @patch("os.listdir")
  @patch("os.path.isfile")
  @patch("shutil.move")
  def test_move_user_custom_actions(self, shutil_move_mock, os_path_isfile_mock, os_listdir_mock, get_ambari_properties_mock):
    properties = Properties()
    properties.process_pair(RESOURCES_DIR_PROPERTY, 'some/test/fake/resources/dir/path')
    get_ambari_properties_mock.return_value = properties
    os_listdir_mock.return_value = ['sometestdir', 'sometestfile.md', 'sometestfile.py', 'sometestfile2.java', 'sometestfile2.py', 'sometestdir2.py']
    os_path_isfile_mock.side_effect = [False, True, True, True, True, False]

    move_user_custom_actions()

    custom_actions_scripts_dir = os.path.join('some/test/fake/resources/dir/path', 'custom_actions', 'scripts')
    shutil_move_mock.assert_has_calls([call(os.path.join('some/test/fake/resources/dir/path', 'custom_actions', 'sometestfile.py'), custom_actions_scripts_dir),
                                       call(os.path.join('some/test/fake/resources/dir/path', 'custom_actions', 'sometestfile2.py'), custom_actions_scripts_dir)])
    self.assertEqual(shutil_move_mock.call_count, 2)

  @patch("ambari_server.serverConfiguration.get_conf_dir")
  @patch("ambari_server.serverConfiguration.get_ambari_classpath")
  @patch("ambari_server.serverUpgrade.run_os_command")
  @patch("ambari_server.serverUpgrade.get_java_exe_path")
  def test_run_stack_upgrade(self, java_exe_path_mock, run_os_command_mock,
                             get_ambari_classpath_mock, get_conf_dir_mock):
    java_exe_path_mock.return_value = "/usr/lib/java/bin/java"
    run_os_command_mock.return_value = (0, None, None)
    get_ambari_classpath_mock.return_value = 'test:path12'
    get_conf_dir_mock.return_value = '/etc/conf'
    stackIdMap = {'HDP' : '2.0'}

    run_stack_upgrade('HDP', '2.0', None, None)

    self.assertTrue(java_exe_path_mock.called)
    self.assertTrue(get_ambari_classpath_mock.called)
    self.assertTrue(get_conf_dir_mock.called)
    self.assertTrue(run_os_command_mock.called)
    run_os_command_mock.assert_called_with('/usr/lib/java/bin/java -cp /etc/conf:test:path12 '
                                          'org.apache.ambari.server.upgrade.StackUpgradeHelper '
                                          'updateStackId ' + "'" + json.dumps(stackIdMap) + "'" +
                                          ' > /var/log/ambari-server/ambari-server.out 2>&1')
    pass

  @patch("ambari_server.serverConfiguration.get_conf_dir")
  @patch("ambari_server.serverConfiguration.get_ambari_classpath")
  @patch("ambari_server.serverUpgrade.run_os_command")
  @patch("ambari_server.serverUpgrade.get_java_exe_path")
  def test_run_stack_upgrade(self, java_exe_path_mock, run_os_command_mock,
                             get_ambari_classpath_mock, get_conf_dir_mock):
    java_exe_path_mock.return_value = "/usr/lib/java/bin/java"
    run_os_command_mock.return_value = (0, None, None)
    get_ambari_classpath_mock.return_value = 'test:path12'
    get_conf_dir_mock.return_value = '/etc/conf'
    stackIdMap = {'HDP' : '2.0', 'repo_url' : 'http://test.com'}

    run_stack_upgrade('HDP', '2.0', 'http://test.com', None)

    self.assertTrue(java_exe_path_mock.called)
    self.assertTrue(get_ambari_classpath_mock.called)
    self.assertTrue(get_conf_dir_mock.called)
    self.assertTrue(run_os_command_mock.called)
    run_os_command_mock.assert_called_with('/usr/lib/java/bin/java -cp /etc/conf:test:path12 '
                                          'org.apache.ambari.server.upgrade.StackUpgradeHelper '
                                          'updateStackId ' + "'" + json.dumps(stackIdMap) + "'" +
                                          ' > /var/log/ambari-server/ambari-server.out 2>&1')
    pass

  @patch("ambari_server.serverConfiguration.get_conf_dir")
  @patch("ambari_server.serverConfiguration.get_ambari_classpath")
  @patch("ambari_server.serverUpgrade.run_os_command")
  @patch("ambari_server.serverUpgrade.get_java_exe_path")
  def test_run_stack_upgrade_with_url_os(self, java_exe_path_mock, run_os_command_mock,
                             get_ambari_classpath_mock, get_conf_dir_mock):
    java_exe_path_mock.return_value = "/usr/lib/java/bin/java"
    run_os_command_mock.return_value = (0, None, None)
    get_ambari_classpath_mock.return_value = 'test:path12'
    get_conf_dir_mock.return_value = '/etc/conf'
    stackIdMap = {'HDP' : '2.0', 'repo_url': 'http://test.com', 'repo_url_os': 'centos5,centos6'}

    run_stack_upgrade('HDP', '2.0', 'http://test.com', 'centos5,centos6')

    self.assertTrue(java_exe_path_mock.called)
    self.assertTrue(get_ambari_classpath_mock.called)
    self.assertTrue(get_conf_dir_mock.called)
    self.assertTrue(run_os_command_mock.called)
    run_os_command_mock.assert_called_with('/usr/lib/java/bin/java -cp /etc/conf:test:path12 '
                                          'org.apache.ambari.server.upgrade.StackUpgradeHelper '
                                          'updateStackId ' + "'" + json.dumps(stackIdMap) + "'" +
                                          ' > /var/log/ambari-server/ambari-server.out 2>&1')
    pass


  @patch("ambari_server.serverConfiguration.get_conf_dir")
  @patch("ambari_server.serverConfiguration.get_ambari_classpath")
  @patch("ambari_server.serverUpgrade.run_os_command")
  @patch("ambari_server.serverUpgrade.get_java_exe_path")
  def test_run_schema_upgrade(self, java_exe_path_mock, run_os_command_mock,
                              get_ambari_classpath_mock, get_conf_dir_mock):
    java_exe_path_mock.return_value = "/usr/lib/java/bin/java"
    run_os_command_mock.return_value = (0, None, None)
    get_ambari_classpath_mock.return_value = 'test:path12'
    get_conf_dir_mock.return_value = '/etc/conf'

    run_schema_upgrade()

    self.assertTrue(java_exe_path_mock.called)
    self.assertTrue(get_ambari_classpath_mock.called)
    self.assertTrue(get_conf_dir_mock.called)
    self.assertTrue(run_os_command_mock.called)
    run_os_command_mock.assert_called_with('/usr/lib/java/bin/java -cp /etc/conf:test:path12 '
                                           'org.apache.ambari.server.upgrade.SchemaUpgradeHelper '
                                           '> /var/log/ambari-server/ambari-server.out 2>&1')
    pass


  @patch("ambari_server.serverConfiguration.get_conf_dir")
  @patch("ambari_server.serverConfiguration.get_ambari_classpath")
  @patch("ambari_server.serverUpgrade.run_os_command")
  @patch("ambari_server.serverUpgrade.get_java_exe_path")
  def test_run_metainfo_upgrade(self, java_exe_path_mock, run_os_command_mock,
                                get_ambari_classpath_mock, get_conf_dir_mock):
    java_exe_path_mock.return_value = "/usr/lib/java/bin/java"
    run_os_command_mock.return_value = (0, None, None)
    get_ambari_classpath_mock.return_value = 'test:path12'
    get_conf_dir_mock.return_value = '/etc/conf'

    json_map = {'a': 'http://newurl'}
    run_metainfo_upgrade(json_map)

    self.assertTrue(java_exe_path_mock.called)
    self.assertTrue(get_ambari_classpath_mock.called)
    self.assertTrue(get_conf_dir_mock.called)
    self.assertTrue(run_os_command_mock.called)
    run_os_command_mock.assert_called_with('/usr/lib/java/bin/java -cp /etc/conf:test:path12 '
                                           'org.apache.ambari.server.upgrade.StackUpgradeHelper updateMetaInfo ' +
                                           "'" + json.dumps(json_map) + "'" +
                                           ' > /var/log/ambari-server/ambari-server.out 2>&1')
    pass


  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("os.path.isfile")
  @patch("ambari_server.serverSetup.get_ambari_properties")
  @patch("os.path.exists")
  @patch("os.path.lexists")
  @patch("os.remove")
  @patch("os.symlink")
  @patch("shutil.copy")
  def test_proceedJDBCProperties(self, copy_mock, os_symlink_mock, os_remove_mock, lexists_mock, exists_mock,
                                 get_ambari_properties_mock, isfile_mock):
    args = MagicMock()

    # test incorrect path to jdbc-driver
    isfile_mock.return_value = False
    args.jdbc_driver = "test jdbc"
    fail = False

    try:
      proceedJDBCProperties(args)
    except FatalException as e:
      self.assertEquals("File test jdbc does not exist!", e.reason)
      fail = True
    self.assertTrue(fail)

    # test incorrect jdbc-db
    isfile_mock.return_value = True
    args.jdbc_db = "incorrect db"
    fail = False

    try:
      proceedJDBCProperties(args)
    except FatalException as e:
      self.assertEquals("Unsupported database name incorrect db. Please see help for more information.", e.reason)
      fail = True
    self.assertTrue(fail)

    # test getAmbariProperties failed
    args.jdbc_db = "mysql"
    get_ambari_properties_mock.return_value = -1
    fail = False

    try:
      proceedJDBCProperties(args)
    except FatalException as e:
      self.assertEquals("Error getting ambari properties", e.reason)
      fail = True
    self.assertTrue(fail)

    # test getAmbariProperties failed
    args.jdbc_db = "mssql"
    get_ambari_properties_mock.return_value = -1
    fail = False

    try:
      proceedJDBCProperties(args)
    except FatalException as e:
      self.assertEquals("Error getting ambari properties", e.reason)
      fail = True
    self.assertTrue(fail)

    # test get resource dir param failed
    args.jdbc_db = "oracle"
    p = MagicMock()
    get_ambari_properties_mock.return_value = p
    p.__getitem__.side_effect = KeyError("test exception")
    exists_mock.return_value = False
    fail = False

    try:
      proceedJDBCProperties(args)
    except FatalException as e:
      fail = True
    self.assertTrue(fail)

    # test copy jdbc failed and symlink exists
    lexists_mock.return_value = True
    args.jdbc_db = "postgres"
    get_ambari_properties_mock.return_value = MagicMock()
    isfile_mock.side_effect = [True, False]
    exists_mock.return_value = True
    fail = False

    def side_effect():
      raise Exception(-1, "Failed to copy!")

    copy_mock.side_effect = side_effect

    try:
      proceedJDBCProperties(args)
    except FatalException as e:
      fail = True
    self.assertTrue(fail)
    self.assertTrue(os_remove_mock.called)

    # test success symlink creation
    get_ambari_properties_mock.reset_mock()
    os_remove_mock.reset_mock()
    p = MagicMock()
    get_ambari_properties_mock.return_value = p
    p.__getitem__.side_effect = None
    p.__getitem__.return_value = "somewhere"
    copy_mock.reset_mock()
    copy_mock.side_effect = None
    isfile_mock.side_effect = [True, False]

    proceedJDBCProperties(args)
    self.assertTrue(os_remove_mock.called)
    self.assertTrue(os_symlink_mock.called)
    self.assertTrue(copy_mock.called)
    self.assertEquals(os_symlink_mock.call_args_list[0][0][0], os.path.join("somewhere","test jdbc"))
    self.assertEquals(os_symlink_mock.call_args_list[0][0][1], os.path.join("somewhere","postgres-jdbc-driver.jar"))
    pass


  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("__builtin__.open")
  @patch("os.path.isfile")
  @patch("os.path.lexists")
  @patch("os.path.exists")
  @patch("os.remove")
  @patch("os.symlink")
  @patch.object(Properties, "store")
  @patch("ambari_server.serverUpgrade.adjust_directory_permissions")
  @patch("ambari_server.serverUpgrade.print_warning_msg")
  @patch("ambari_server.serverUpgrade.read_ambari_user")
  @patch("ambari_server.serverUpgrade.run_schema_upgrade")
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  @patch("ambari_server.serverConfiguration.find_properties_file")
  @patch("ambari_server.serverUpgrade.update_ambari_properties")
  @patch("ambari_server.serverUpgrade.is_root")
  @patch("ambari_server.serverConfiguration.write_property")
  @patch("ambari_server.serverConfiguration.get_ambari_version")
  @patch("ambari_server.dbConfiguration.get_ambari_properties")
  @patch("ambari_server.serverConfiguration.get_ambari_properties")
  @patch("ambari_server.serverUpgrade.get_ambari_properties")
  @patch("ambari_server.serverUpgrade.upgrade_local_repo")
  @patch("ambari_server.serverUpgrade.move_user_custom_actions")
  def test_upgrade_from_161(self, move_user_custom_actions_mock, upgrade_local_repo_mock, get_ambari_properties_mock,
                            get_ambari_properties_2_mock, get_ambari_properties_3_mock, get_ambari_version_mock, write_property_mock,
                            is_root_mock, update_ambari_properties_mock, find_properties_file_mock, run_os_command_mock,
                            run_schema_upgrade_mock, read_ambari_user_mock, print_warning_msg_mock,
                            adjust_directory_permissions_mock, properties_store_mock,
                            os_symlink_mock, os_remove_mock, exists_mock, lexists_mock, isfile_mock, open_mock):

    def reset_mocks():
      run_os_command_mock.reset_mock()
      write_property_mock.reset_mock()
      isfile_mock.reset_mock()
      lexists_mock.reeset_mock()
      os_symlink_mock.reset_mock()

      lexists_mock.return_value = False

      args = MagicMock()

      del args.dbms
      del args.database_index
      del args.database_host
      del args.database_port
      del args.database_name
      del args.database_username
      del args.database_password
      del args.sid_or_sname
      del args.jdbc_url

      args.jdbc_driver= None
      args.jdbc_db = None

      args.silent = False

      return args

    args = reset_mocks()
    args.dbms = "postgres"

    is_root_mock.return_value = True
    update_ambari_properties_mock.return_value = 0
    get_ambari_version_mock.return_value = "1.7.0"
    move_user_custom_actions_mock.return_value = None

    # Local Postgres
    # In Ambari 1.6.1 for an embedded postgres database, the "server.jdbc.database" property stored the DB name,
    # and the DB type was assumed to be "postgres" if the "server.persistence.type" property was "local"
    properties = Properties()
    properties.process_pair(PERSISTENCE_TYPE_PROPERTY, "local")
    properties.process_pair(JDBC_DATABASE_PROPERTY, "ambari")
    properties.process_pair(RESOURCES_DIR_PROPERTY, "/tmp")
    get_ambari_properties_mock.return_value = properties

    properties2 = Properties()
    properties2.process_pair(PERSISTENCE_TYPE_PROPERTY, "local")
    properties2.process_pair(JDBC_DATABASE_NAME_PROPERTY, "ambari")
    properties2.process_pair(JDBC_DATABASE_PROPERTY, "postgres")
    get_ambari_properties_3_mock.side_effect = get_ambari_properties_2_mock.side_effect = [properties, properties2, properties2]

    run_schema_upgrade_mock.return_value = 0
    read_ambari_user_mock.return_value = "custom_user"

    run_os_command_mock.return_value = (0, "", "")
    isfile_mock.return_value = False

    try:
      upgrade(args)
    except FatalException as fe:
      self.fail("Did not expect failure: " + str(fe))
    else:
      self.assertTrue(write_property_mock.called)
      self.assertEquals(write_property_mock.call_args_list[0][0][0], JDBC_DATABASE_NAME_PROPERTY)
      self.assertEquals(write_property_mock.call_args_list[0][0][1], "ambari")
      self.assertEquals(write_property_mock.call_args_list[1][0][0], JDBC_DATABASE_PROPERTY)
      self.assertEquals(write_property_mock.call_args_list[1][0][1], "postgres")
      self.assertTrue(run_os_command_mock.called)
      self.assertFalse(move_user_custom_actions_mock.called)

    args = reset_mocks()

    # External Postgres
    # In Ambari 1.6.1 for an external postgres database, the "server.jdbc.database" property stored the
    # DB type ("postgres"), and the "server.jdbc.schema" property stored the DB name.
    properties = Properties()
    properties.process_pair(PERSISTENCE_TYPE_PROPERTY, "remote")
    properties.process_pair(JDBC_DATABASE_PROPERTY, "postgres")
    properties.process_pair(JDBC_RCA_SCHEMA_PROPERTY, "ambari")
    properties.process_pair(JDBC_URL_PROPERTY, "jdbc:postgresql://c6410.ambari.apache.org:5432/ambari")

    properties2 = Properties()
    properties2.process_pair(PERSISTENCE_TYPE_PROPERTY, "remote")
    properties2.process_pair(JDBC_DATABASE_NAME_PROPERTY, "ambari")
    properties2.process_pair(JDBC_DATABASE_PROPERTY, "postgres")
    properties2.process_pair(JDBC_RCA_SCHEMA_PROPERTY, "ambari")
    properties2.process_pair(JDBC_URL_PROPERTY, "jdbc:postgresql://c6410.ambari.apache.org:5432/ambari")

    get_ambari_properties_mock.return_value = properties
    get_ambari_properties_3_mock.side_effect = get_ambari_properties_2_mock.side_effect = [properties, properties2, properties2]

    exists_mock.return_value = True

    try:
      upgrade(args)
    except FatalException as fe:
      self.fail("Did not expect failure: " + str(fe))
    else:
      self.assertTrue(write_property_mock.called)
      self.assertFalse(run_os_command_mock.called)
      self.assertFalse(move_user_custom_actions_mock.called)

    args = reset_mocks()

    # External Postgres missing DB type, so it should be set based on the JDBC URL.
    properties = Properties()
    properties.process_pair(PERSISTENCE_TYPE_PROPERTY, "remote")
    properties.process_pair(JDBC_RCA_SCHEMA_PROPERTY, "ambari")
    properties.process_pair(JDBC_URL_PROPERTY, "jdbc:postgresql://c6410.ambari.apache.org:5432/ambari")

    get_ambari_properties_mock.return_value = properties
    get_ambari_properties_3_mock.side_effect = get_ambari_properties_2_mock.side_effect = [properties, properties2, properties2]

    try:
      upgrade(args)
    except FatalException as fe:
      self.fail("Did not expect failure: " + str(fe))
    else:
      self.assertTrue(write_property_mock.call_count == 2)
      self.assertFalse(move_user_custom_actions_mock.called)

    args = reset_mocks()

    # External MySQL
    # In Ambari 1.6.1 for an external MySQL database, the "server.jdbc.database" property stored the DB type ("mysql"),
    # And the "server.jdbc.schema" property stored the DB name.
    properties = Properties()
    properties.process_pair(PERSISTENCE_TYPE_PROPERTY, "remote")
    properties.process_pair(JDBC_DATABASE_PROPERTY, "mysql")
    properties.process_pair(JDBC_RCA_SCHEMA_PROPERTY, "ambari")
    properties.process_pair(JDBC_URL_PROPERTY, "jdbc:mysql://c6409.ambari.apache.org:3306/ambari")

    properties2 = Properties()
    properties2.process_pair(PERSISTENCE_TYPE_PROPERTY, "remote")
    properties2.process_pair(JDBC_DATABASE_PROPERTY, "mysql")
    properties2.process_pair(JDBC_DATABASE_NAME_PROPERTY, "ambari")
    properties2.process_pair(JDBC_RCA_SCHEMA_PROPERTY, "ambari")
    properties2.process_pair(JDBC_URL_PROPERTY, "jdbc:mysql://c6409.ambari.apache.org:3306/ambari")

    get_ambari_properties_mock.return_value = properties
    get_ambari_properties_3_mock.side_effect = get_ambari_properties_2_mock.side_effect = [properties, properties2, properties2]

    isfile_mock.side_effect = [False, True, False]

    try:
      upgrade(args)
    except FatalException as fe:
      self.fail("Did not expect failure: " + str(fe))
    else:
      self.assertTrue(write_property_mock.called)
      self.assertFalse(move_user_custom_actions_mock.called)
      self.assertTrue(os_symlink_mock.called)
      self.assertTrue(os_symlink_mock.call_args_list[0][0][0] == "/var/lib/ambari-server/resources/mysql-connector-java.jar")
      self.assertTrue(os_symlink_mock.call_args_list[0][0][1] == "/var/lib/ambari-server/resources/mysql-jdbc-driver.jar")

    args = reset_mocks()

    # External MySQL missing DB type, so it should be set based on the JDBC URL.
    properties = Properties()
    properties.process_pair(PERSISTENCE_TYPE_PROPERTY, "remote")
    properties.process_pair(JDBC_RCA_SCHEMA_PROPERTY, "ambari")
    properties.process_pair(JDBC_URL_PROPERTY, "jdbc:mysql://c6409.ambari.apache.org:3306/ambari")

    get_ambari_properties_mock.return_value = properties
    get_ambari_properties_3_mock.side_effect = get_ambari_properties_2_mock.side_effect = [properties, properties2, properties2]

    isfile_mock.side_effect = None

    try:
      upgrade(args)
    except FatalException as fe:
      self.fail("Did not expect failure: " + str(fe))
    else:
      self.assertTrue(write_property_mock.call_count == 2)
      self.assertFalse(move_user_custom_actions_mock.called)
    pass


  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("__builtin__.open")
  @patch("os.path.isfile")
  @patch("os.path.exists")
  @patch("os.path.lexists")
  @patch("os.remove")
  @patch("os.symlink")
  @patch.object(Properties, "store")
  @patch.object(PGConfig, "_change_db_files_owner")
  @patch("ambari_server.serverConfiguration.find_properties_file")
  @patch("ambari_server.serverUpgrade.adjust_directory_permissions")
  @patch("ambari_server.serverUpgrade.print_warning_msg")
  @patch("ambari_server.serverUpgrade.read_ambari_user")
  @patch("ambari_server.serverUpgrade.run_schema_upgrade")
  @patch("ambari_server.serverUpgrade.update_ambari_properties")
  @patch("ambari_server.serverUpgrade.parse_properties_file")
  @patch("ambari_server.serverUpgrade.get_ambari_version")
  @patch("ambari_server.serverConfiguration.get_ambari_version")
  @patch("ambari_server.serverUpgrade.is_root")
  @patch("ambari_server.dbConfiguration.get_ambari_properties")
  @patch("ambari_server.serverConfiguration.get_ambari_properties")
  @patch("ambari_server.serverUpgrade.get_ambari_properties")
  @patch("ambari_server.serverUpgrade.upgrade_local_repo")
  @patch("ambari_server.serverUpgrade.move_user_custom_actions")
  def test_upgrade(self, move_user_custom_actions, upgrade_local_repo_mock,
                   get_ambari_properties_mock, get_ambari_properties_2_mock, get_ambari_properties_3_mock,
                   is_root_mock, get_ambari_version_mock, get_ambari_version_2_mock,
                   parse_properties_file_mock,
                   update_ambari_properties_mock, run_schema_upgrade_mock,
                   read_ambari_user_mock, print_warning_msg_mock,
                   adjust_directory_permissions_mock,
                   find_properties_file_mock, change_db_files_owner_mock, properties_store_mock,
                   os_symlink_mock, os_remove_mock, lexists_mock, exists_mock, isfile_mock, open_mock):

    def reset_mocks():
      isfile_mock.reset_mock()

      args = MagicMock()
      del args.database_index
      del args.dbms
      del args.database_host
      del args.database_port
      del args.database_name
      del args.database_username
      del args.database_password
      del args.persistence_type
      del args.sid_or_sname
      del args.jdbc_url

      args.must_set_database_options = True

      return args

    args = reset_mocks()

    properties = Properties()
    get_ambari_properties_3_mock.return_value = get_ambari_properties_2_mock.return_value = \
      get_ambari_properties_mock.return_value = properties
    update_ambari_properties_mock.return_value = 0
    run_schema_upgrade_mock.return_value = 0
    isfile_mock.return_value = False
    get_ambari_version_2_mock.return_value = get_ambari_version_mock.return_value = CURR_AMBARI_VERSION
    move_user_custom_actions.return_value = None

    # Testing call under non-root
    is_root_mock.return_value = False
    try:
      upgrade(args)
      self.fail("Should throw exception")
    except FatalException as fe:
      # Expected
      self.assertTrue("root-level" in fe.reason)
      pass

    args = reset_mocks()

    # Testing calls under root
    is_root_mock.return_value = True

    # Testing with undefined custom user
    read_ambari_user_mock.return_value = None
    run_schema_upgrade_mock.return_value = 0
    change_db_files_owner_mock.return_value = 0
    exists_mock.return_value = True
    upgrade(args)
    self.assertTrue(print_warning_msg_mock.called)
    warning_args = print_warning_msg_mock.call_args[0][0]
    self.assertTrue("custom ambari user" in warning_args)
    self.assertTrue(upgrade_local_repo_mock.called)
    self.assertTrue(move_user_custom_actions.called)

    args = reset_mocks()

    # Testing with defined custom user
    read_ambari_user_mock.return_value = "ambari-custom-user"
    upgrade(args)
    self.assertTrue(adjust_directory_permissions_mock.called)

    args = reset_mocks()

    run_schema_upgrade_mock.return_value = 0
    parse_properties_file_mock.called = False
    move_user_custom_actions.called = False
    retcode = upgrade(args)
    self.assertTrue(get_ambari_properties_mock.called)
    self.assertTrue(get_ambari_properties_2_mock.called)

    self.assertNotEqual(-1, retcode)
    self.assertTrue(parse_properties_file_mock.called)
    self.assertTrue(run_schema_upgrade_mock.called)
    self.assertTrue(move_user_custom_actions.called)

    # Assert that move_user_custom_actions is called on upgrade to Ambari == 2.0.0
    get_ambari_version_2_mock.return_value = get_ambari_version_mock.return_value = '2.0.0'
    move_user_custom_actions.called = False
    upgrade(args)
    self.assertTrue(move_user_custom_actions.called)

    # Assert that move_user_custom_actions is not called on upgrade to Ambari < 2.0.0
    get_ambari_version_2_mock.return_value = get_ambari_version_mock.return_value = '1.6.0'
    move_user_custom_actions.called = False
    upgrade(args)
    self.assertFalse(move_user_custom_actions.called)

    get_ambari_version_2_mock.return_value = get_ambari_version_mock.return_value = CURR_AMBARI_VERSION

    # test getAmbariProperties failed
    args = reset_mocks()

    get_ambari_properties_3_mock.return_value = get_ambari_properties_2_mock.return_value = \
      get_ambari_properties_mock.return_value = -1
    fail = False

    try:
      upgrade(args)
    except FatalException as e:
      self.assertEquals("Error getting ambari properties", e.reason)
      fail = True
    self.assertTrue(fail)

    # test get resource dir param failed
    args = reset_mocks()

    p = MagicMock()
    get_ambari_properties_mock.reset_mock()
    get_ambari_properties_2_mock.reset_mock()
    get_ambari_properties_3_mock.reset_mock()
    get_ambari_properties_3_mock.return_value = get_ambari_properties_2_mock.return_value = \
      get_ambari_properties_mock.return_value = p
    p.__getitem__.side_effect = ["something", "something", "something", KeyError("test exception")]
    exists_mock.return_value = False
    fail = False

    try:
      upgrade(args)
    except FatalException as e:
      fail = True
    self.assertTrue(fail)

    # test if some drivers are available in resources, and symlink available too
    args = reset_mocks()

    props = Properties()
    props.process_pair(JDBC_DATABASE_NAME_PROPERTY, "something")
    props.process_pair(RESOURCES_DIR_PROPERTY, "resources")

    get_ambari_properties_3_mock.return_value = get_ambari_properties_2_mock.return_value = \
      get_ambari_properties_mock.return_value = props
    exists_mock.return_value = True
    lexists_mock.return_value = True
    isfile_mock.side_effect = [True, False, False]

    upgrade(args)
    self.assertTrue(os_remove_mock.called)
    self.assertEquals(os_remove_mock.call_count, 1)
    self.assertEquals(os_remove_mock.call_args[0][0], os.path.join("resources", "oracle-jdbc-driver.jar"))
    self.assertEquals(os_symlink_mock.call_count, 1)
    self.assertEquals(os_symlink_mock.call_args[0][0], os.path.join("resources", "ojdbc6.jar"))
    self.assertEquals(os_symlink_mock.call_args[0][1], os.path.join("resources", "oracle-jdbc-driver.jar"))
    pass


  def test_print_info_msg(self):
    out = StringIO.StringIO()
    sys.stdout = out

    set_verbose(True)
    print_info_msg("msg")
    self.assertNotEqual("", out.getvalue())

    sys.stdout = sys.__stdout__
    pass


  def test_print_error_msg(self):

    out = StringIO.StringIO()
    sys.stdout = out

    set_verbose(True)
    print_error_msg("msg")
    self.assertNotEqual("", out.getvalue())

    sys.stdout = sys.__stdout__
    pass


  def test_print_warning_msg(self):

    out = StringIO.StringIO()
    sys.stdout = out

    set_verbose(True)
    print_warning_msg("msg")
    self.assertNotEqual("", out.getvalue())

    sys.stdout = sys.__stdout__
    pass


  @patch("ambari_server.userInput.get_choice_string_input")
  def test_get_YN_input(self, get_choice_string_input_mock):

    get_YN_input("prompt", "default")
    self.assertTrue(get_choice_string_input_mock.called)
    self.assertEqual(4, len(get_choice_string_input_mock.call_args_list[0][0]))
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(_ambari_server_, "setup")
  def test_main_db_options(self, setup_mock):
    base_args = ["ambari-server.py", "setup"]
    db_args = ["--database", "postgres", "--databasehost", "somehost.net", "--databaseport", "12345",
               "--databasename", "ambari", "--databaseusername", "ambari", "--databasepassword", "bigdata"]

    #test no args
    failed = False
    sys.argv = list(base_args)

    try:
      _ambari_server_.mainBody()
    except SystemExit:
      failed = True
      pass

    self.assertFalse(failed)
    self.assertTrue(setup_mock.called)
    self.assertTrue(setup_mock.call_args_list[0][0][0].must_set_database_options)

    setup_mock.reset_mock()

    # test embedded option
    failed = False
    sys.argv = list(base_args)
    sys.argv.extend(db_args[-10:])
    sys.argv.extend(["--database", "embedded"])

    try:
      _ambari_server_.mainBody()
    except SystemExit:
      failed = True
      pass

    self.assertFalse(failed)
    self.assertTrue(setup_mock.called)

    setup_mock.reset_mock()

    #test full args
    sys.argv = list(base_args)
    sys.argv.extend(db_args)

    try:
      _ambari_server_.mainBody()
    except SystemExit:
      failed = True
      pass

    self.assertFalse(failed)
    self.assertTrue(setup_mock.called)
    self.assertFalse(setup_mock.call_args_list[0][0][0].must_set_database_options)

    setup_mock.reset_mock()

    #test not full args
    sys.argv = list(base_args)
    sys.argv.extend(["--database", "postgres"])

    try:
      _ambari_server_.mainBody()
    except SystemExit:
      failed = True
      pass

    self.assertFalse(setup_mock.called)
    self.assertTrue(failed)

    setup_mock.reset_mock()

    #test wrong database
    failed = False
    sys.argv = list(base_args)
    sys.argv.extend(["--database", "unknown"])
    sys.argv.extend(db_args[2:])

    try:
      _ambari_server_.mainBody()
    except SystemExit:
      failed = True
      pass

    self.assertTrue(failed)
    self.assertFalse(setup_mock.called)

    setup_mock.reset_mock()

    #test wrong port check
    failed = False
    sys.argv = list(base_args)
    sys.argv.extend(["--databaseport", "unknown"])
    sys.argv.extend(db_args[:4])
    sys.argv.extend(db_args[6:])

    try:
      _ambari_server_.mainBody()
    except SystemExit:
      failed = True
      pass

    self.assertTrue(failed)
    self.assertFalse(setup_mock.called)
    pass


  @not_for_platform(PLATFORM_WINDOWS)
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_server.serverSetup.get_YN_input")
  @patch("ambari_server.dbConfiguration.get_validated_string_input")
  @patch("ambari_server.dbConfiguration_linux.print_info_msg")
  def test_prompt_db_properties(self, print_info_msg_mock,
                                get_validated_string_input_mock, get_YN_input_mock):
    def reset_mocks():
      get_validated_string_input_mock.reset_mock()
      get_YN_input_mock.reset_mock()

      args = MagicMock()

      del args.database_index
      del args.dbms
      del args.database_host
      del args.database_port
      del args.database_name
      del args.database_username
      del args.database_password
      del args.persistence_type

      return args

    args = reset_mocks()

    set_silent(False)

    #test not prompt
    args.must_set_database_options = False
    prompt_db_properties(args)

    self.assertFalse(get_validated_string_input_mock.called)
    self.assertFalse(get_YN_input_mock.called)

    args = reset_mocks()

    #test prompt
    args.must_set_database_options = True
    get_YN_input_mock.return_value = False

    prompt_db_properties(args)
    self.assertTrue(get_YN_input_mock.called)
    self.assertFalse(get_validated_string_input_mock.called)

    args = reset_mocks()

    #test prompt advanced
    args.must_set_database_options = True
    get_YN_input_mock.return_value = True
    get_validated_string_input_mock.return_value = "4"

    prompt_db_properties(args)
    self.assertTrue(get_YN_input_mock.called)
    self.assertTrue(get_validated_string_input_mock.called)

    self.assertEquals(args.database_index, 3)
    pass

  @patch("ambari_server.serverConfiguration.get_conf_dir")
  def test_update_ambari_properties(self, get_conf_dir_mock):
    from ambari_server import serverConfiguration   # need to modify constants inside the module

    properties = ["server.jdbc.user.name=ambari-server\n",
                  "server.jdbc.user.passwd=/etc/ambari-server/conf/password.dat\n",
                  "java.home=/usr/jdk64/jdk1.6.0_31\n",
                  "server.jdbc.database_name=ambari\n",
                  "ambari-server.user=ambari\n",
                  "agent.fqdn.service.url=URL\n"]

    NEW_PROPERTY = 'some_new_property=some_value\n'
    CHANGED_VALUE_PROPERTY = 'server.jdbc.database_name=should_not_overwrite_value\n'

    get_conf_dir_mock.return_value = '/etc/ambari-server/conf'

    (tf1, fn1) = tempfile.mkstemp()
    (tf2, fn2) = tempfile.mkstemp()
    configDefaults.AMBARI_PROPERTIES_BACKUP_FILE = fn1
    serverConfiguration.AMBARI_PROPERTIES_FILE = fn2

    with open(serverConfiguration.AMBARI_PROPERTIES_FILE, "w") as f:
      f.write(NEW_PROPERTY)
      f.write(CHANGED_VALUE_PROPERTY)
      f.close()

    with open(configDefaults.AMBARI_PROPERTIES_BACKUP_FILE, 'w') as f:
      for line in properties:
        f.write(line)
      f.close()

    #Call tested method
    update_ambari_properties()

    timestamp = datetime.datetime.now()
    #RPMSAVE_FILE wasn't found
    self.assertFalse(os.path.exists(configDefaults.AMBARI_PROPERTIES_BACKUP_FILE))
    #Renamed RPMSAVE_FILE exists
    self.assertTrue(os.path.exists(configDefaults.AMBARI_PROPERTIES_BACKUP_FILE
                                   + '.' + timestamp.strftime('%Y%m%d%H%M%S')))

    with open(serverConfiguration.AMBARI_PROPERTIES_FILE, 'r') as f:
      ambari_properties_content = f.readlines()

    for line in properties:
      if (line == "agent.fqdn.service.url=URL\n"):
        if (not GET_FQDN_SERVICE_URL + "=URL\n" in ambari_properties_content) and (
          line in ambari_properties_content):
          self.fail()
      else:
        if not line in ambari_properties_content:
          self.fail()

    if not NEW_PROPERTY in ambari_properties_content:
      self.fail()

    if CHANGED_VALUE_PROPERTY in ambari_properties_content:
      self.fail()

    # Command should not fail if *.rpmsave file is missing
    result = update_ambari_properties()
    self.assertEquals(result, 0)

    os.unlink(fn2)

    #if ambari.properties file is absent then "ambari-server upgrade" should
    # fail
    (tf, fn) = tempfile.mkstemp()
    configDefaults.AMBARI_PROPERTIES_BACKUP_FILE = fn

    result = update_ambari_properties()
    self.assertNotEquals(result, 0)
    pass

  @patch("ambari_server.properties.Properties.__init__")
  @patch("ambari_server.serverConfiguration.search_file")
  def test_update_ambari_properties_negative_case(self, search_file_mock, properties_mock):
    search_file_mock.return_value = None
    #Call tested method
    self.assertEquals(0, update_ambari_properties())
    self.assertFalse(properties_mock.called)

    search_file_mock.return_value = False
    #Call tested method
    self.assertEquals(0, update_ambari_properties())
    self.assertFalse(properties_mock.called)

    search_file_mock.return_value = ''
    #Call tested method
    self.assertEquals(0, update_ambari_properties())
    self.assertFalse(properties_mock.called)
    pass


  @patch("ambari_server.serverConfiguration.get_conf_dir")
  def test_update_ambari_properties_without_some_properties(self, get_conf_dir_mock):
    '''
      Checks: update_ambari_properties call should add ambari-server.user property if
      it's absent
    '''
    from ambari_server import serverConfiguration   # need to modify constants inside the module

    properties = ["server.jdbc.user.name=ambari-server\n",
                  "server.jdbc.user.passwd=/etc/ambari-server/conf/password.dat\n",
                  "java.home=/usr/jdk64/jdk1.6.0_31\n",
                  "server.os_type=redhat6\n"]

    get_conf_dir_mock.return_value = '/etc/ambari-server/conf'

    (tf1, fn1) = tempfile.mkstemp()
    (tf2, fn2) = tempfile.mkstemp()
    serverConfiguration.AMBARI_PROPERTIES_RPMSAVE_FILE = fn1
    serverConfiguration.AMBARI_PROPERTIES_FILE = fn2

    with open(serverConfiguration.AMBARI_PROPERTIES_RPMSAVE_FILE, 'w') as f:
      for line in properties:
        f.write(line)

    #Call tested method
    update_ambari_properties()

    ambari_properties = Properties()
    ambari_properties.load(open(fn2))

    self.assertTrue(NR_USER_PROPERTY in ambari_properties.keys())
    value = ambari_properties[NR_USER_PROPERTY]
    self.assertEqual(value, "root")
    self.assertTrue(OS_FAMILY_PROPERTY in ambari_properties.keys())

    os.unlink(fn2)
    pass


  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_commons.firewall.run_os_command")
  @patch("ambari_server.serverSetup.verify_setup_allowed")
  @patch("sys.exit")
  @patch("ambari_server.serverSetup.get_YN_input")
  @patch("ambari_server.dbConfiguration.get_validated_string_input")
  @patch("ambari_server.dbConfiguration_linux.get_YN_input")
  @patch("ambari_server.dbConfiguration_linux.get_validated_string_input")
  @patch("ambari_server.dbConfiguration_linux.PGConfig._store_remote_properties")
  @patch("ambari_server.dbConfiguration_linux.LinuxDBMSConfig.ensure_jdbc_driver_installed")
  @patch("ambari_server.dbConfiguration_linux.read_password")
  @patch("ambari_server.serverSetup.check_jdbc_drivers")
  @patch("ambari_server.serverSetup.is_root")
  @patch("ambari_server.serverSetup.check_ambari_user")
  @patch("ambari_server.serverSetup.download_and_install_jdk")
  @patch("ambari_server.serverSetup.configure_os_settings")
  @patch('__builtin__.raw_input')
  @patch("ambari_server.serverSetup.disable_security_enhancements")
  @patch("ambari_server.serverSetup.expand_jce_zip_file")
  def test_setup_remote_db_wo_client(self, expand_jce_zip_file_mock, check_selinux_mock, raw_input, configure_os_settings_mock,
                                     download_jdk_mock, check_ambari_user_mock, is_root_mock, check_jdbc_drivers_mock,
                                     read_password_mock, ensure_jdbc_driver_installed_mock, store_remote_properties_mock,
                                     get_validated_string_input_0_mock, get_YN_input_0_mock,
                                     get_validated_string_input_mock, get_YN_input,
                                     exit_mock, verify_setup_allowed_method,
                                     run_os_command_mock):
    args = MagicMock()

    args.jdbc_driver = None
    args.jdbc_db = None
    args.silent = False

    del args.dbms
    del args.database_index
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password
    del args.persistence_type

    raw_input.return_value = ""
    is_root_mock.return_value = True
    check_selinux_mock.return_value = (0, "")
    run_os_command_mock.return_value = 3,"",""
    store_remote_properties_mock.return_value = 0
    get_YN_input.return_value = True
    get_validated_string_input_mock.side_effect = ["4"]
    get_validated_string_input_0_mock.side_effect = ["localhost", "5432", "ambari", "ambari", "admin"]
    get_YN_input_0_mock.return_value = False
    read_password_mock.return_value = "encrypted_bigdata"
    ensure_jdbc_driver_installed_mock.return_value = True
    check_jdbc_drivers_mock.return_value = 0
    check_ambari_user_mock.return_value = (0, False, 'user', None)
    download_jdk_mock.return_value = 0
    configure_os_settings_mock.return_value = 0
    verify_setup_allowed_method.return_value = 0
    expand_jce_zip_file_mock.return_value = 0

    try:
      setup(args)
      self.fail("Should throw exception")
    except NonFatalException as fe:
      # Expected
      self.assertTrue("Remote database setup aborted." in fe.reason)
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_commons.firewall.run_os_command")
  @patch("sys.exit")
  @patch("ambari_server.userInput.get_YN_input")
  @patch("ambari_commons.os_utils.is_root")
  @patch("ambari_server.dbConfiguration_linux.store_password_file")
  @patch("__builtin__.raw_input")
  def test_store_remote_properties(self, raw_input_mock, store_password_file_mock,
                                   is_root_mock, get_YN_input, exit_mock,
                                   run_os_command_mock
  ):
    raw_input_mock.return_value = ""
    is_root_mock.return_value = True
    get_YN_input.return_value = False
    run_os_command_mock.return_value = 3,"",""
    store_password_file_mock.return_value = "encrypted_bigdata"

    import optparse

    args = optparse.Values()
    args.dbms = "oracle"
    args.database_host = "localhost"
    args.database_port = "1234"
    args.database_name = "ambari"
    args.postgres_schema = "ambari"
    args.sid_or_sname = "foo"
    args.database_username = "foo"
    args.database_password = "foo"

    properties0 = Properties()
    properties = Properties()

    factory = DBMSConfigFactory()
    dbConfig = factory.create(args, properties0)

    dbConfig._store_remote_properties(properties)

    found = False
    for n in properties.propertyNames():
      if not found and n.startswith("server.jdbc.properties"):
        found = True

    self.assertTrue(found)
    pass


  @not_for_platform(PLATFORM_WINDOWS)
  @patch("ambari_server.serverConfiguration.find_properties_file")
  def test_get_ambari_properties(self, find_properties_file_mock):

    find_properties_file_mock.return_value = None
    rcode = get_ambari_properties()
    self.assertEqual(rcode, -1)

    tf1 = tempfile.NamedTemporaryFile()
    find_properties_file_mock.return_value = tf1.name
    prop_name = 'name'
    prop_value = 'val'

    with open(tf1.name, 'w') as fout:
      fout.write(prop_name + '=' + prop_value)
    fout.close()

    properties = get_ambari_properties()

    self.assertEqual(properties[prop_name], prop_value)
    pass


  @only_for_platform(PLATFORM_WINDOWS)
  @patch("ambari_server.serverConfiguration.find_properties_file")
  def test_get_ambari_properties(self, find_properties_file):

    find_properties_file.return_value = None
    rcode = get_ambari_properties()
    self.assertEqual(rcode, -1)

    tf1 = tempfile.NamedTemporaryFile()
    find_properties_file.return_value = tf1.name
    prop_name = 'name'
    prop_value = 'val'

    with open(tf1.name, 'w') as fout:
      fout.write(prop_name + '=' + prop_value)
    fout.close()

    properties = get_ambari_properties()

    self.assertEqual(properties[prop_name], prop_value)
    self.assertEqual(properties.fileName, os.path.abspath(tf1.name))

    sys.stdout = sys.__stdout__
    pass


  @patch("os.path.exists")
  @patch("os.remove")
  @patch("ambari_commons.os_utils.print_warning_msg")
  def test_remove_file(self, printWarningMsgMock, removeMock, pathExistsMock):
    def side_effect():
      raise Exception(-1, "Failed to delete!")

    removeMock.side_effect = side_effect
    pathExistsMock.return_value = 1

    res = remove_file("/someNonExsistantDir/filename")
    self.assertEquals(res, 1)

    removeMock.side_effect = None
    res = remove_file("/someExsistantDir/filename")
    self.assertEquals(res, 0)

  @patch("shutil.copyfile")
  def test_copy_file(self, shutilCopyfileMock):
    def side_effect():
      raise Exception(-1, "Failed to copy!")

    shutilCopyfileMock.side_effect = side_effect

    try:
      copy_file("/tmp/psswd", "/someNonExsistantDir/filename")
      self.fail("Exception on file not copied has not been thrown!")
    except FatalException:
      # Expected
      pass

    self.assertTrue(shutilCopyfileMock.called)

    shutilCopyfileMock.side_effect = None
    try:
      copy_file("/tmp/psswd", "/root/psswd")
    except FatalException:
      self.fail("Exception on file copied should not be thrown!")

    self.assertTrue(shutilCopyfileMock.called)
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_server.dbConfiguration_linux.get_ambari_properties")
  @patch("ambari_server.dbConfiguration_linux.print_error_msg")
  @patch("ambari_server.dbConfiguration.print_error_msg")
  @patch("ambari_server.dbConfiguration_linux.print_warning_msg")
  @patch("__builtin__.raw_input")
  @patch("glob.glob")
  @patch("os.path.isdir")
  @patch("os.path.lexists")
  @patch("os.remove")
  @patch("os.symlink")
  @patch("shutil.copy")
  def test_ensure_jdbc_drivers_installed(self, shutil_copy_mock, os_symlink_mock, os_remove_mock, lexists_mock, isdir_mock, glob_mock,
                              raw_input_mock, print_warning_msg, print_error_msg_mock, print_error_msg_2_mock,
                              get_ambari_properties_mock):
    out = StringIO.StringIO()
    sys.stdout = out

    def reset_mocks():
      get_ambari_properties_mock.reset_mock()
      shutil_copy_mock.reset_mock()
      print_error_msg_mock.reset_mock()
      print_warning_msg.reset_mock()
      raw_input_mock.reset_mock()

      args = MagicMock()

      del args.database_index
      del args.persistence_type
      del args.silent
      del args.sid_or_sname
      del args.jdbc_url

      args.dbms = "oracle"

      return args

    # Check positive scenario
    drivers_list = [os.path.join(os.sep,'usr','share','java','ojdbc6.jar')]
    resources_dir = os.sep + 'tmp'

    props = Properties()
    props.process_pair(RESOURCES_DIR_PROPERTY, resources_dir)
    get_ambari_properties_mock.return_value = props

    factory = DBMSConfigFactory()

    args = reset_mocks()
    glob_mock.return_value = drivers_list
    isdir_mock.return_value = True

    lexists_mock.return_value = True

    dbms = factory.create(args, props)
    rcode = dbms.ensure_jdbc_driver_installed(props)

    self.assertEquals(os_symlink_mock.call_count, 1)
    self.assertEquals(os_symlink_mock.call_args_list[0][0][0], os.path.join(os.sep,'tmp','ojdbc6.jar'))
    self.assertEquals(os_symlink_mock.call_args_list[0][0][1], os.path.join(os.sep,'tmp','oracle-jdbc-driver.jar'))
    self.assertTrue(rcode)
    self.assertEquals(shutil_copy_mock.call_count, 1)
    self.assertEquals(shutil_copy_mock.call_args_list[0][0][0], drivers_list[0])
    self.assertEquals(shutil_copy_mock.call_args_list[0][0][1], resources_dir)

    # Check negative scenarios
    # Silent option, no drivers
    set_silent(True)

    args = reset_mocks()
    glob_mock.return_value = []

    failed = False

    try:
      dbms = factory.create(args, props)
      rcode = dbms.ensure_jdbc_driver_installed(props)
    except FatalException:
      failed = True

    self.assertTrue(print_error_msg_mock.called)
    self.assertTrue(failed)

    # Non-Silent option, no drivers
    set_silent(False)

    args = reset_mocks()
    glob_mock.return_value = []

    failed = False

    try:
      dbms = factory.create(args, props)
      rcode = dbms.ensure_jdbc_driver_installed(props)
    except FatalException:
      failed = True

    self.assertTrue(failed)
    self.assertTrue(print_error_msg_mock.called)

    # Non-Silent option, no drivers at first ask, present drivers after that
    args = reset_mocks()

    glob_mock.side_effect = [[], drivers_list]

    dbms = factory.create(args, props)
    rcode = dbms.ensure_jdbc_driver_installed(props)

    self.assertTrue(rcode)
    self.assertEquals(shutil_copy_mock.call_count, 1)
    self.assertEquals(shutil_copy_mock.call_args_list[0][0][0], drivers_list[0])
    self.assertEquals(shutil_copy_mock.call_args_list[0][0][1], resources_dir)

    # Non-Silent option, no drivers at first ask, no drivers after that
    args = reset_mocks()
    glob_mock.side_effect = [[], []]

    failed = False

    try:
      dbms = factory.create(args, props)
      rcode = dbms.ensure_jdbc_driver_installed(props)
    except FatalException:
      failed = True

    self.assertTrue(failed)
    self.assertTrue(print_error_msg_mock.called)

    # Failed to copy_files
    args = reset_mocks()
    glob_mock.side_effect = [drivers_list]

    try:
      dbms = factory.create(args, props)
      rcode = dbms.ensure_jdbc_driver_installed(props)
    except FatalException:
      failed = True

    self.assertTrue(failed)

    sys.stdout = sys.__stdout__
    pass


  @not_for_platform(PLATFORM_WINDOWS)
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_server.dbConfiguration.get_ambari_properties")
  @patch("os.path.isdir")
  @patch("os.path.isfile")
  @patch("os.path.lexists")
  @patch("os.remove")
  @patch("os.symlink")
  def test_check_jdbc_drivers(self, os_symlink_mock, os_remove_mock, lexists_mock, isfile_mock, isdir_mock,
                              get_ambari_properties_mock):
    args = MagicMock()

    # Check positive scenario
    drivers_list = [os.path.join(os.sep,'usr','share','java','ojdbc6.jar')]
    resources_dir = os.sep + 'tmp'

    props = Properties()
    props.process_pair(RESOURCES_DIR_PROPERTY, resources_dir)
    get_ambari_properties_mock.return_value = props

    isdir_mock.return_value = True

    isfile_mock.side_effect = [True, False, False]

    del args.database_index
    del args.persistence_type
    del args.silent
    del args.sid_or_sname
    del args.jdbc_url

    lexists_mock.return_value = True

    check_jdbc_drivers(args)

    self.assertEquals(os_symlink_mock.call_count, 1)
    self.assertEquals(os_symlink_mock.call_args_list[0][0][0], os.path.join(os.sep,'tmp','ojdbc6.jar'))
    self.assertEquals(os_symlink_mock.call_args_list[0][0][1], os.path.join(os.sep,'tmp','oracle-jdbc-driver.jar'))

    # Check negative scenarios

    # No drivers deployed
    get_ambari_properties_mock.reset_mock()
    os_symlink_mock.reset_mock()

    isfile_mock.side_effect = [False, False, False]

    check_jdbc_drivers(args)

    self.assertFalse(os_symlink_mock.called)

    pass

  @patch("ambari_server.serverConfiguration.find_properties_file")
  def test_get_ambari_properties(self, find_properties_file_mock):

    find_properties_file_mock.return_value = None
    rcode = get_ambari_properties()
    self.assertEqual(rcode, -1)

    tf1 = tempfile.NamedTemporaryFile()
    find_properties_file_mock.return_value = tf1.name
    prop_name = 'name'
    prop_value = 'val'

    with open(tf1.name, 'w') as fout:
      fout.write(prop_name + '=' + prop_value)
    fout.close()

    properties = get_ambari_properties()

    self.assertEqual(properties[prop_name], prop_value)
    self.assertEqual(properties.fileName, os.path.abspath(tf1.name))

    sys.stdout = sys.__stdout__
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch("ambari_server.serverConfiguration.check_database_name_property")
  @patch("ambari_server.serverConfiguration.find_properties_file")
  def test_parse_properties_file(self, find_properties_file_mock, check_database_name_property_mock):

    check_database_name_property_mock.return_value = 1

    tf1 = tempfile.NamedTemporaryFile(mode='r')
    find_properties_file_mock.return_value = tf1.name

    args = MagicMock()
    parse_properties_file(args)
    self.assertEquals(args.persistence_type, "local")

    with open(tf1.name, 'w') as fout:
      fout.write("\n")
      fout.write(PERSISTENCE_TYPE_PROPERTY + "=remote")

    args = MagicMock()

    parse_properties_file(args)
    self.assertEquals(args.persistence_type, "remote")
    pass


  @not_for_platform(PLATFORM_WINDOWS)
  @patch("os.path.isabs")
  @patch("ambari_server.dbConfiguration.decrypt_password_for_alias")
  @patch("ambari_server.dbConfiguration_linux.get_ambari_properties")
  def test_configure_database_username_password_masterkey_persisted(self,
                                                                    get_ambari_properties_method,
                                                                    decrypt_password_for_alias_method,
                                                                    path_isabs_method):

    out = StringIO.StringIO()
    sys.stdout = out

    properties = Properties()
    properties.process_pair(JDBC_USER_NAME_PROPERTY, "fakeuser")
    properties.process_pair(JDBC_PASSWORD_PROPERTY, "${alias=somealias}")
    properties.process_pair(JDBC_DATABASE_NAME_PROPERTY, "fakedbname")
    properties.process_pair(SECURITY_KEY_IS_PERSISTED, "True")

    get_ambari_properties_method.return_value = properties
    decrypt_password_for_alias_method.return_value = "falepasswd"

    args = MagicMock()
    args.master_key = None

    del args.database_index
    del args.dbms
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password
    del args.sid_or_sname
    del args.jdbc_url

    dbms = OracleConfig(args, properties, "local")

    self.assertTrue(decrypt_password_for_alias_method.called)
    self.assertFalse(path_isabs_method.called)
    self.assertEquals("fakeuser", dbms.database_username)
    self.assertEquals("falepasswd", dbms.database_password)

    sys.stdout = sys.__stdout__
    pass


  @not_for_platform(PLATFORM_WINDOWS)
  @patch("ambari_server.dbConfiguration_linux.read_password")
  def test_configure_database_password(self, read_password_method):

    out = StringIO.StringIO()
    sys.stdout = out

    read_password_method.return_value = "fakepasswd"

    result = LinuxDBMSConfig._configure_database_password(True)
    self.assertTrue(read_password_method.called)
    self.assertEquals("fakepasswd", result)

    result = LinuxDBMSConfig._configure_database_password(True)
    self.assertEquals("fakepasswd", result)

    result = LinuxDBMSConfig._configure_database_password(True)
    self.assertEquals("fakepasswd", result)

    sys.stdout = sys.__stdout__
    pass


  @patch("os.path.exists")
  @patch("ambari_server.setupSecurity.get_is_secure")
  @patch("ambari_server.setupSecurity.get_is_persisted")
  @patch("ambari_server.setupSecurity.remove_password_file")
  @patch("ambari_server.setupSecurity.save_passwd_for_alias")
  @patch("ambari_server.setupSecurity.read_master_key")
  @patch("ambari_server.setupSecurity.read_ambari_user")
  @patch("ambari_server.setupSecurity.get_master_key_location")
  @patch("ambari_server.setupSecurity.update_properties_2")
  @patch("ambari_server.setupSecurity.save_master_key")
  @patch("ambari_server.setupSecurity.get_YN_input")
  @patch("ambari_server.setupSecurity.search_file")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.is_root")
  def test_setup_master_key_not_persist(self, is_root_method,
                                        get_ambari_properties_method, search_file_message,
                                        get_YN_input_method, save_master_key_method,
                                        update_properties_method, get_master_key_location_method,
                                        read_ambari_user_method, read_master_key_method,
                                        save_passwd_for_alias_method, remove_password_file_method,
                                        get_is_persisted_method, get_is_secure_method, exists_mock):

    is_root_method.return_value = True

    p = Properties()
    FAKE_PWD_STRING = "fakepasswd"
    p.process_pair(JDBC_PASSWORD_PROPERTY, FAKE_PWD_STRING)
    p.process_pair(LDAP_MGR_PASSWORD_PROPERTY, FAKE_PWD_STRING)
    p.process_pair(SSL_TRUSTSTORE_PASSWORD_PROPERTY, FAKE_PWD_STRING)
    p.process_pair(JDBC_RCA_PASSWORD_FILE_PROPERTY, FAKE_PWD_STRING)
    get_ambari_properties_method.return_value = p

    read_master_key_method.return_value = "aaa"
    get_YN_input_method.return_value = False
    read_ambari_user_method.return_value = None
    save_passwd_for_alias_method.return_value = 0
    get_is_persisted_method.return_value = (True, "filepath")
    get_is_secure_method.return_value = False
    exists_mock.return_value = False

    setup_master_key()

    self.assertTrue(get_YN_input_method.called)
    self.assertTrue(read_master_key_method.called)
    self.assertTrue(read_ambari_user_method.called)
    self.assertTrue(update_properties_method.called)
    self.assertFalse(save_master_key_method.called)
    self.assertTrue(save_passwd_for_alias_method.called)
    self.assertEquals(3, save_passwd_for_alias_method.call_count)
    self.assertTrue(remove_password_file_method.called)

    result_expected = {JDBC_PASSWORD_PROPERTY:
                         get_alias_string(JDBC_RCA_PASSWORD_ALIAS),
                       JDBC_RCA_PASSWORD_FILE_PROPERTY:
                         get_alias_string(JDBC_RCA_PASSWORD_ALIAS),
                       LDAP_MGR_PASSWORD_PROPERTY:
                         get_alias_string(LDAP_MGR_PASSWORD_ALIAS),
                       SSL_TRUSTSTORE_PASSWORD_PROPERTY:
                         get_alias_string(SSL_TRUSTSTORE_PASSWORD_ALIAS),
                       SECURITY_IS_ENCRYPTION_ENABLED: 'true'}

    sorted_x = sorted(result_expected.iteritems(), key=operator.itemgetter(0))
    sorted_y = sorted(update_properties_method.call_args[0][1].iteritems(),
                      key=operator.itemgetter(0))
    self.assertEquals(sorted_x, sorted_y)
    pass


  @patch("ambari_server.setupSecurity.save_passwd_for_alias")
  @patch("os.path.exists")
  @patch("ambari_server.setupSecurity.get_is_secure")
  @patch("ambari_server.setupSecurity.get_is_persisted")
  @patch("ambari_server.setupSecurity.read_master_key")
  @patch("ambari_server.setupSecurity.read_ambari_user")
  @patch("ambari_server.setupSecurity.get_master_key_location")
  @patch("ambari_server.setupSecurity.update_properties_2")
  @patch("ambari_server.setupSecurity.save_master_key")
  @patch("ambari_server.setupSecurity.get_YN_input")
  @patch("ambari_server.serverConfiguration.search_file")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.is_root")
  def test_setup_master_key_persist(self, is_root_method,
                                    get_ambari_properties_method, search_file_message,
                                    get_YN_input_method, save_master_key_method,
                                    update_properties_method, get_master_key_location_method,
                                    read_ambari_user_method, read_master_key_method,
                                    get_is_persisted_method, get_is_secure_method, exists_mock,
                                    save_passwd_for_alias_method):

    is_root_method.return_value = True

    p = Properties()
    FAKE_PWD_STRING = "fakepasswd"
    p.process_pair(JDBC_PASSWORD_PROPERTY, FAKE_PWD_STRING)
    get_ambari_properties_method.return_value = p

    read_master_key_method.return_value = "aaa"
    get_YN_input_method.side_effect = [True, False]
    read_ambari_user_method.return_value = None
    get_is_persisted_method.return_value = (True, "filepath")
    get_is_secure_method.return_value = False
    exists_mock.return_value = False
    save_passwd_for_alias_method.return_value = 0

    setup_master_key()

    self.assertTrue(get_YN_input_method.called)
    self.assertTrue(read_master_key_method.called)
    self.assertTrue(read_ambari_user_method.called)
    self.assertTrue(update_properties_method.called)
    self.assertTrue(save_master_key_method.called)

    result_expected = {JDBC_PASSWORD_PROPERTY:
                        get_alias_string(JDBC_RCA_PASSWORD_ALIAS),
                        SECURITY_IS_ENCRYPTION_ENABLED: 'true'}

    sorted_x = sorted(result_expected.iteritems(), key=operator.itemgetter(0))
    sorted_y = sorted(update_properties_method.call_args[0][1].iteritems(),
                      key=operator.itemgetter(0))
    self.assertEquals(sorted_x, sorted_y)
    pass


  @patch("ambari_server.setupSecurity.read_master_key")
  @patch("ambari_server.setupSecurity.remove_password_file")
  @patch("os.path.exists")
  @patch("ambari_server.setupSecurity.read_ambari_user")
  @patch("ambari_server.setupSecurity.get_master_key_location")
  @patch("ambari_server.setupSecurity.save_passwd_for_alias")
  @patch("ambari_server.setupSecurity.read_passwd_for_alias")
  @patch("ambari_server.setupSecurity.update_properties_2")
  @patch("ambari_server.setupSecurity.save_master_key")
  @patch("ambari_server.setupSecurity.get_validated_string_input")
  @patch("ambari_server.setupSecurity.get_YN_input")
  @patch("ambari_server.setupSecurity.search_file")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.is_root")
  def test_reset_master_key_persisted(self, is_root_method,
                                      get_ambari_properties_method, search_file_message,
                                      get_YN_input_method, get_validated_string_input_method,
                                      save_master_key_method, update_properties_method,
                                      read_passwd_for_alias_method, save_passwd_for_alias_method,
                                      get_master_key_location_method,
                                      read_ambari_user_method, exists_mock,
                                      remove_password_file_method, read_master_key_method):

    # Testing call under non-root
    is_root_method.return_value = False
    try:
      setup_master_key()
      self.fail("Should throw exception")
    except FatalException as fe:
      # Expected
      self.assertTrue("root-level" in fe.reason)
      pass

    # Testing call under root
    is_root_method.return_value = True

    search_file_message.return_value = "filepath"
    read_ambari_user_method.return_value = None

    p = Properties()
    FAKE_PWD_STRING = '${alias=fakealias}'
    p.process_pair(JDBC_PASSWORD_PROPERTY, FAKE_PWD_STRING)
    p.process_pair(LDAP_MGR_PASSWORD_PROPERTY, FAKE_PWD_STRING)
    p.process_pair(SSL_TRUSTSTORE_PASSWORD_PROPERTY, FAKE_PWD_STRING)
    p.process_pair(JDBC_RCA_PASSWORD_FILE_PROPERTY, FAKE_PWD_STRING)
    get_ambari_properties_method.return_value = p

    get_YN_input_method.side_effect = [True, True]
    read_master_key_method.return_value = "aaa"
    read_passwd_for_alias_method.return_value = "fakepassword"
    save_passwd_for_alias_method.return_value = 0
    exists_mock.return_value = False

    setup_master_key()

    self.assertTrue(save_master_key_method.called)
    self.assertTrue(get_YN_input_method.called)
    self.assertTrue(read_master_key_method.called)
    self.assertTrue(update_properties_method.called)
    self.assertTrue(read_passwd_for_alias_method.called)
    self.assertTrue(3, read_passwd_for_alias_method.call_count)
    self.assertTrue(3, save_passwd_for_alias_method.call_count)

    result_expected = {JDBC_PASSWORD_PROPERTY:
                         get_alias_string(JDBC_RCA_PASSWORD_ALIAS),
                       JDBC_RCA_PASSWORD_FILE_PROPERTY:
                         get_alias_string(JDBC_RCA_PASSWORD_ALIAS),
                       LDAP_MGR_PASSWORD_PROPERTY:
                         get_alias_string(LDAP_MGR_PASSWORD_ALIAS),
                       SSL_TRUSTSTORE_PASSWORD_PROPERTY:
                         get_alias_string(SSL_TRUSTSTORE_PASSWORD_ALIAS),
                       SECURITY_IS_ENCRYPTION_ENABLED: 'true'}

    sorted_x = sorted(result_expected.iteritems(), key=operator.itemgetter(0))
    sorted_y = sorted(update_properties_method.call_args[0][1].iteritems(),
                      key=operator.itemgetter(0))
    self.assertEquals(sorted_x, sorted_y)
    pass


  @patch("ambari_server.setupSecurity.get_is_persisted")
  @patch("ambari_server.setupSecurity.get_is_secure")
  @patch("ambari_server.setupSecurity.remove_password_file")
  @patch("os.path.exists")
  @patch("ambari_server.setupSecurity.read_ambari_user")
  @patch("ambari_server.setupSecurity.get_master_key_location")
  @patch("ambari_server.setupSecurity.save_passwd_for_alias")
  @patch("ambari_server.setupSecurity.read_passwd_for_alias")
  @patch("ambari_server.setupSecurity.update_properties_2")
  @patch("ambari_server.setupSecurity.save_master_key")
  @patch("ambari_server.setupSecurity.get_validated_string_input")
  @patch("ambari_server.setupSecurity.get_YN_input")
  @patch("ambari_server.setupSecurity.search_file")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.is_root")
  def test_reset_master_key_not_persisted(self, is_root_method,
                                          get_ambari_properties_method,
                                          search_file_message, get_YN_input_method,
                                          get_validated_string_input_method, save_master_key_method,
                                          update_properties_method, read_passwd_for_alias_method,
                                          save_passwd_for_alias_method,
                                          get_master_key_location_method, read_ambari_user_method,
                                          exists_mock, remove_password_file_method, get_is_secure_method,
                                          get_is_persisted_method):

    is_root_method.return_value = True
    search_file_message.return_value = False
    read_ambari_user_method.return_value = None

    p = Properties()
    FAKE_PWD_STRING = '${alias=fakealias}'
    p.process_pair(JDBC_PASSWORD_PROPERTY, FAKE_PWD_STRING)
    p.process_pair(LDAP_MGR_PASSWORD_PROPERTY, FAKE_PWD_STRING)
    p.process_pair(SSL_TRUSTSTORE_PASSWORD_PROPERTY, FAKE_PWD_STRING)
    p.process_pair(JDBC_RCA_PASSWORD_FILE_PROPERTY, FAKE_PWD_STRING)
    get_ambari_properties_method.return_value = p

    get_YN_input_method.side_effect = [True, False]
    get_validated_string_input_method.return_value = "aaa"
    read_passwd_for_alias_method.return_value = "fakepassword"
    save_passwd_for_alias_method.return_value = 0
    exists_mock.return_value = False
    get_is_secure_method.return_value = True
    get_is_persisted_method.return_value = (True, "filePath")

    setup_master_key()

    self.assertFalse(save_master_key_method.called)
    self.assertTrue(get_YN_input_method.called)
    self.assertTrue(get_validated_string_input_method.called)
    self.assertTrue(update_properties_method.called)
    self.assertTrue(read_passwd_for_alias_method.called)
    self.assertTrue(3, read_passwd_for_alias_method.call_count)
    self.assertTrue(3, save_passwd_for_alias_method.call_count)
    self.assertFalse(save_master_key_method.called)

    result_expected = {JDBC_PASSWORD_PROPERTY:
                         get_alias_string(JDBC_RCA_PASSWORD_ALIAS),
                       JDBC_RCA_PASSWORD_FILE_PROPERTY:
                         get_alias_string(JDBC_RCA_PASSWORD_ALIAS),
                       LDAP_MGR_PASSWORD_PROPERTY:
                         get_alias_string(LDAP_MGR_PASSWORD_ALIAS),
                       SSL_TRUSTSTORE_PASSWORD_PROPERTY:
                         get_alias_string(SSL_TRUSTSTORE_PASSWORD_ALIAS),
                       SECURITY_IS_ENCRYPTION_ENABLED: 'true'}

    sorted_x = sorted(result_expected.iteritems(), key=operator.itemgetter(0))
    sorted_y = sorted(update_properties_method.call_args[0][1].iteritems(),
                      key=operator.itemgetter(0))
    self.assertEquals(sorted_x, sorted_y)
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("__builtin__.raw_input")
  @patch("ambari_server.setupSecurity.get_is_secure")
  @patch("ambari_server.setupSecurity.get_YN_input")
  @patch("ambari_server.setupSecurity.update_properties_2")
  @patch("ambari_server.setupSecurity.search_file")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.is_root")
  def test_setup_ldap_invalid_input(self, is_root_method, get_ambari_properties_method,
                                    search_file_message,
                                    update_properties_method,
                                    get_YN_input_method,
                                    get_is_secure_method,
                                    raw_input_mock):
    out = StringIO.StringIO()
    sys.stdout = out
    is_root_method.return_value = True
    search_file_message.return_value = "filepath"

    configs = {SECURITY_MASTER_KEY_LOCATION: "filepath",
               SECURITY_KEYS_DIR: tempfile.gettempdir(),
               SECURITY_IS_ENCRYPTION_ENABLED: "true"
    }

    get_ambari_properties_method.return_value = configs
    raw_input_mock.side_effect = ['a:3', 'b:b', 'hody', 'b:2', 'false', 'user', 'uid', 'group', 'cn', 'member', 'dn', 'base', 'follow', 'true']
    set_silent(False)
    get_YN_input_method.return_value = True

    setup_ldap()

    ldap_properties_map = \
      {
        LDAP_PRIMARY_URL_PROPERTY: "a:3",
        "authentication.ldap.secondaryUrl": "b:2",
        "authentication.ldap.useSSL": "false",
        "authentication.ldap.userObjectClass": "user",
        "authentication.ldap.usernameAttribute": "uid",
        "authentication.ldap.groupObjectClass": "group",
        "authentication.ldap.groupNamingAttr": "cn",
        "authentication.ldap.groupMembershipAttr": "member",
        "authentication.ldap.dnAttribute": "dn",
        "authentication.ldap.baseDn": "base",
        "authentication.ldap.referral": "follow",
        "authentication.ldap.bindAnonymously": "true",
        "client.security": "ldap",
        "ambari.ldap.isConfigured": "true"
      }

    sorted_x = sorted(ldap_properties_map.iteritems(), key=operator.itemgetter(0))
    sorted_y = sorted(update_properties_method.call_args[0][1].iteritems(),
                      key=operator.itemgetter(0))
    self.assertEquals(sorted_x, sorted_y)
    self.assertTrue(get_YN_input_method.called)
    self.assertTrue(8, raw_input_mock.call_count)

    raw_input_mock.reset_mock()
    raw_input_mock.side_effect = ['a:3', '', 'b:2', 'false', 'user', 'uid', 'group', 'cn', 'member', 'dn', 'base', 'follow', 'true']

    setup_ldap()

    ldap_properties_map = \
      {
        LDAP_PRIMARY_URL_PROPERTY: "a:3",
        "authentication.ldap.useSSL": "false",
        "authentication.ldap.userObjectClass": "user",
        "authentication.ldap.usernameAttribute": "uid",
        "authentication.ldap.groupObjectClass": "group",
        "authentication.ldap.groupNamingAttr": "cn",
        "authentication.ldap.groupMembershipAttr": "member",
        "authentication.ldap.dnAttribute": "dn",
        "authentication.ldap.baseDn": "base",
        "authentication.ldap.referral": "follow",
        "authentication.ldap.bindAnonymously": "true",
        "client.security": "ldap",
        "ambari.ldap.isConfigured": "true"
      }

    sorted_x = sorted(ldap_properties_map.iteritems(), key=operator.itemgetter(0))
    sorted_y = sorted(update_properties_method.call_args[0][1].iteritems(),
                      key=operator.itemgetter(0))
    self.assertEquals(sorted_x, sorted_y)
    self.assertTrue(5, raw_input_mock.call_count)

    sys.stdout = sys.__stdout__
    pass

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_server.setupSecurity.get_is_secure")
  @patch("ambari_server.setupSecurity.encrypt_password")
  @patch("ambari_server.setupSecurity.save_passwd_for_alias")
  @patch("ambari_server.setupSecurity.get_YN_input")
  @patch("ambari_server.setupSecurity.update_properties_2")
  @patch("ambari_server.setupSecurity.configure_ldap_password")
  @patch("ambari_server.setupSecurity.get_validated_string_input")
  @patch("ambari_server.serverConfiguration.search_file")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.is_root")
  @patch("ambari_server.setupSecurity.read_password")
  @patch("os.path.exists")
  def test_setup_ldap(self, exists_method, read_password_method, is_root_method, get_ambari_properties_method,
                      search_file_message,
                      get_validated_string_input_method,
                      configure_ldap_password_method, update_properties_method,
                      get_YN_input_method, save_passwd_for_alias_method,
                      encrypt_password_method, get_is_secure_method):
    out = StringIO.StringIO()
    sys.stdout = out


    # Testing call under non-root
    is_root_method.return_value = False
    try:
      setup_ldap()
      self.fail("Should throw exception")
    except FatalException as fe:
      # Expected
      self.assertTrue("root-level" in fe.reason)
      pass

    # Testing call under root
    is_root_method.return_value = True

    search_file_message.return_value = "filepath"

    configs = {SECURITY_MASTER_KEY_LOCATION: "filepath",
               SECURITY_KEYS_DIR: tempfile.gettempdir(),
               SECURITY_IS_ENCRYPTION_ENABLED: "true"
    }

    get_ambari_properties_method.return_value = configs
    configure_ldap_password_method.return_value = "password"
    save_passwd_for_alias_method.return_value = 0
    encrypt_password_method.return_value = get_alias_string(LDAP_MGR_PASSWORD_ALIAS)

    def yn_input_side_effect(*args, **kwargs):
      if 'TrustStore' in args[0]:
        return False
      else:
        return True

    #get_YN_input_method.side_effect = yn_input_side_effect()
    get_YN_input_method.side_effect = [True, ]

    def valid_input_side_effect(*args, **kwargs):
      if 'Bind anonymously' in args[0]:
        return 'false'
      if args[1] == "true" or args[1] == "false":
        return args[1]
      else:
        return "test"

    get_validated_string_input_method.side_effect = valid_input_side_effect

    setup_ldap()

    ldap_properties_map = \
      {
        "authentication.ldap.primaryUrl": "test",
        "authentication.ldap.secondaryUrl": "test",
        "authentication.ldap.useSSL": "false",
        "authentication.ldap.userObjectClass": "test",
        "authentication.ldap.usernameAttribute": "test",
        "authentication.ldap.baseDn": "test",
        "authentication.ldap.bindAnonymously": "false",
        "authentication.ldap.managerDn": "test",
        "authentication.ldap.groupObjectClass": "test",
        "authentication.ldap.groupMembershipAttr": "test",
        "authentication.ldap.groupNamingAttr": "test",
        "authentication.ldap.dnAttribute": "test",
        "authentication.ldap.referral": "test",
        "client.security": "ldap", \
        LDAP_MGR_PASSWORD_PROPERTY: "ldap-password.dat",
        "ambari.ldap.isConfigured": "true"
      }

    sorted_x = sorted(ldap_properties_map.iteritems(), key=operator.itemgetter(0))
    sorted_y = sorted(update_properties_method.call_args[0][1].iteritems(),
                      key=operator.itemgetter(0))
    self.assertEquals(sorted_x, sorted_y)
    self.assertTrue(update_properties_method.called)
    self.assertTrue(configure_ldap_password_method.called)
    self.assertTrue(get_validated_string_input_method.called)
    self.assertTrue(get_YN_input_method.called)

    # truststore not found case

    def os_path_exists(*args, **kwargs):
      if "bogus" in args[0]:
        return False
      else:
        return True
      pass

    def input_enable_ssl(*args, **kwargs):
      if 'Bind anonymously' in args[0]:
        return 'false'
      if "SSL" in args[0]:
        return "true"
      if "Path to TrustStore file" in args[0]:
        if input_enable_ssl.path_counter < 2:
          input_enable_ssl.path_counter += 1
          return "bogus"
        else:
          return "valid"
      if args[1] == "true" or args[1] == "false":
        return args[1]
      else:
        return "test"
      pass

    input_enable_ssl.path_counter = 0

    exists_method.side_effect = os_path_exists
    get_validated_string_input_method.side_effect = input_enable_ssl
    read_password_method.return_value = "password"
    get_YN_input_method.reset_mock()
    get_YN_input_method.side_effect = [True, True]
    update_properties_method.reset_mock()

    setup_ldap()

    self.assertTrue(read_password_method.called)

    ldap_properties_map = \
      {
        "authentication.ldap.primaryUrl": "test",
        "authentication.ldap.secondaryUrl": "test",
        "authentication.ldap.useSSL": "true",
        "authentication.ldap.usernameAttribute": "test",
        "authentication.ldap.baseDn": "test",
        "authentication.ldap.dnAttribute": "test",
        "authentication.ldap.bindAnonymously": "false",
        "authentication.ldap.managerDn": "test",
        "client.security": "ldap",
        "ssl.trustStore.type": "test",
        "ssl.trustStore.path": "valid",
        "ssl.trustStore.password": "password",
        LDAP_MGR_PASSWORD_PROPERTY: get_alias_string(LDAP_MGR_PASSWORD_ALIAS)
      }

    sorted_x = sorted(ldap_properties_map.iteritems(), key=operator.itemgetter(0))
    sorted_y = sorted(update_properties_method.call_args[0][1].iteritems(),
                      key=operator.itemgetter(0))

    sys.stdout = sys.__stdout__
    pass

  @patch("urllib2.urlopen")
  @patch("ambari_server.setupSecurity.get_validated_string_input")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.is_server_runing")
  @patch("ambari_server.setupSecurity.is_root")
  def test_ldap_sync_all(self, is_root_method, is_server_runing_mock, get_ambari_properties_mock,
      get_validated_string_input_mock, urlopen_mock):

    is_root_method.return_value = True
    is_server_runing_mock.return_value = (True, 0)
    properties = Properties()
    properties.process_pair(IS_LDAP_CONFIGURED, 'true')
    properties.process_pair(CLIENT_API_PORT_PROPERTY, '8080')
    get_ambari_properties_mock.return_value = properties
    get_validated_string_input_mock.side_effect = ['admin', 'admin']

    response = MagicMock()
    response.getcode.side_effect = [201, 200, 200]
    response.read.side_effect = ['{"resources" : [{"href" : "http://c6401.ambari.apache.org:8080/api/v1/ldap_sync_events/16","Event" : {"id" : 16}}]}',
                          '{"Event":{"status" : "RUNNING","summary" : {"groups" : {"created" : 0,"removed" : 0,"updated" : 0},"memberships" : {"created" : 0,"removed" : 0},"users" : {"created" : 0,"removed" : 0,"updated" : 0}}}}',
                          '{"Event":{"status" : "COMPLETE","summary" : {"groups" : {"created" : 1,"removed" : 0,"updated" : 0},"memberships" : {"created" : 5,"removed" : 0},"users" : {"created" : 5,"removed" : 0,"updated" : 0}}}}']

    urlopen_mock.return_value = response

    options = MagicMock()
    options.ldap_sync_all = True
    options.ldap_sync_existing = False
    options.ldap_sync_users = None
    options.ldap_sync_groups = None

    sync_ldap(options)

    url = '{0}://{1}:{2!s}{3}'.format('http', '127.0.0.1', '8080', '/api/v1/ldap_sync_events')
    request = urlopen_mock.call_args_list[0][0][0]

    self.assertEquals(url, str(request.get_full_url()))
    self.assertEquals('[{"Event": {"specs": [{"principal_type": "users", "sync_type": "all"}, {"principal_type": "groups", "sync_type": "all"}]}}]', request.data)

    self.assertTrue(response.getcode.called)
    self.assertTrue(response.read.called)
    pass

  @patch("__builtin__.open")
  @patch("os.path.exists")
  @patch("urllib2.urlopen")
  @patch("ambari_server.setupSecurity.get_validated_string_input")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.is_server_runing")
  @patch("ambari_server.setupSecurity.is_root")
  def test_ldap_sync_users(self, is_root_method, is_server_runing_mock, get_ambari_properties_mock,
                         get_validated_string_input_mock, urlopen_mock, os_path_exists_mock, open_mock):

    os_path_exists_mock.return_value = 1
    f = MagicMock()
    f.__enter__().read.return_value = "bob, tom"

    open_mock.return_value = f
    is_root_method.return_value = True
    is_server_runing_mock.return_value = (True, 0)
    properties = Properties()
    properties.process_pair(IS_LDAP_CONFIGURED, 'true')
    get_ambari_properties_mock.return_value = properties
    get_validated_string_input_mock.side_effect = ['admin', 'admin']

    response = MagicMock()
    response.getcode.side_effect = [201, 200, 200]
    response.read.side_effect = ['{"resources" : [{"href" : "http://c6401.ambari.apache.org:8080/api/v1/ldap_sync_events/16","Event" : {"id" : 16}}]}',
                                 '{"Event":{"status" : "RUNNING","summary" : {"groups" : {"created" : 0,"removed" : 0,"updated" : 0},"memberships" : {"created" : 0,"removed" : 0},"users" : {"created" : 0,"removed" : 0,"updated" : 0}}}}',
                                 '{"Event":{"status" : "COMPLETE","summary" : {"groups" : {"created" : 1,"removed" : 0,"updated" : 0},"memberships" : {"created" : 5,"removed" : 0},"users" : {"created" : 5,"removed" : 0,"updated" : 0}}}}']

    urlopen_mock.return_value = response

    options = MagicMock()
    options.ldap_sync_all = False
    options.ldap_sync_existing = False
    options.ldap_sync_users = 'users.txt'
    options.ldap_sync_groups = None

    sync_ldap(options)

    request = urlopen_mock.call_args_list[0][0][0]

    self.assertEquals('[{"Event": {"specs": [{"principal_type": "users", "sync_type": "specific", "names": "bob, tom"}]}}]', request.data)

    self.assertTrue(response.getcode.called)
    self.assertTrue(response.read.called)
    pass

  @patch("__builtin__.open")
  @patch("os.path.exists")
  @patch("urllib2.urlopen")
  @patch("ambari_server.setupSecurity.get_validated_string_input")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.is_server_runing")
  @patch("ambari_server.setupSecurity.is_root")
  def test_ldap_sync_groups(self, is_root_method, is_server_runing_mock, get_ambari_properties_mock,
                           get_validated_string_input_mock, urlopen_mock, os_path_exists_mock, open_mock):

    os_path_exists_mock.return_value = 1
    f = MagicMock()
    f.__enter__().read.return_value = "group1, group2"

    open_mock.return_value = f
    is_root_method.return_value = True
    is_server_runing_mock.return_value = (True, 0)
    properties = Properties()
    properties.process_pair(IS_LDAP_CONFIGURED, 'true')
    get_ambari_properties_mock.return_value = properties
    get_validated_string_input_mock.side_effect = ['admin', 'admin']

    response = MagicMock()
    response.getcode.side_effect = [201, 200, 200]
    response.read.side_effect = ['{"resources" : [{"href" : "http://c6401.ambari.apache.org:8080/api/v1/ldap_sync_events/16","Event" : {"id" : 16}}]}',
                                 '{"Event":{"status" : "RUNNING","summary" : {"groups" : {"created" : 0,"removed" : 0,"updated" : 0},"memberships" : {"created" : 0,"removed" : 0},"users" : {"created" : 0,"removed" : 0,"updated" : 0}}}}',
                                 '{"Event":{"status" : "COMPLETE","summary" : {"groups" : {"created" : 1,"removed" : 0,"updated" : 0},"memberships" : {"created" : 5,"removed" : 0},"users" : {"created" : 5,"removed" : 0,"updated" : 0}}}}']

    urlopen_mock.return_value = response

    options = MagicMock()
    options.ldap_sync_all = False
    options.ldap_sync_existing = False
    options.ldap_sync_users = None
    options.ldap_sync_groups = 'groups.txt'

    sync_ldap(options)

    request = urlopen_mock.call_args_list[0][0][0]

    self.assertEquals('[{"Event": {"specs": [{"principal_type": "groups", "sync_type": "specific", "names": "group1, group2"}]}}]', request.data)

    self.assertTrue(response.getcode.called)
    self.assertTrue(response.read.called)
    pass

  @patch("urllib2.urlopen")
  @patch("ambari_server.setupSecurity.get_validated_string_input")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.is_server_runing")
  @patch("ambari_server.setupSecurity.is_root")
  def test_ldap_sync_ssl(self, is_root_method, is_server_runing_mock, get_ambari_properties_mock,
                         get_validated_string_input_mock, urlopen_mock):

    is_root_method.return_value = True
    is_server_runing_mock.return_value = (True, 0)
    properties = Properties()
    properties.process_pair(IS_LDAP_CONFIGURED, 'true')
    properties.process_pair(SSL_API, 'true')
    properties.process_pair(SSL_API_PORT, '8443')
    get_ambari_properties_mock.return_value = properties
    get_validated_string_input_mock.side_effect = ['admin', 'admin']


    response = MagicMock()
    response.getcode.side_effect = [201, 200, 200]
    response.read.side_effect = ['{"resources" : [{"href" : "https://c6401.ambari.apache.org:8443/api/v1/ldap_sync_events/16","Event" : {"id" : 16}}]}',
                                 '{"Event":{"status" : "RUNNING","summary" : {"groups" : {"created" : 0,"removed" : 0,"updated" : 0},"memberships" : {"created" : 0,"removed" : 0},"users" : {"created" : 0,"removed" : 0,"updated" : 0}}}}',
                                 '{"Event":{"status" : "COMPLETE","summary" : {"groups" : {"created" : 1,"removed" : 0,"updated" : 0},"memberships" : {"created" : 5,"removed" : 0},"users" : {"created" : 5,"removed" : 0,"updated" : 0}}}}']

    urlopen_mock.return_value = response

    options = MagicMock()
    options.ldap_sync_all = True
    options.ldap_sync_existing = False
    options.ldap_sync_users = None
    options.ldap_sync_groups = None

    sync_ldap(options)

    url = '{0}://{1}:{2!s}{3}'.format('https', '127.0.0.1', '8443', '/api/v1/ldap_sync_events')
    request = urlopen_mock.call_args_list[0][0][0]

    self.assertEquals(url, str(request.get_full_url()))

    self.assertTrue(response.getcode.called)
    self.assertTrue(response.read.called)
    pass

  @patch("urllib2.urlopen")
  @patch("ambari_server.setupSecurity.get_validated_string_input")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.is_server_runing")
  @patch("ambari_server.setupSecurity.is_root")
  def test_ldap_sync_existing(self, is_root_method, is_server_runing_mock, get_ambari_properties_mock,
                         get_validated_string_input_mock, urlopen_mock):

    is_root_method.return_value = True
    is_server_runing_mock.return_value = (True, 0)
    properties = Properties()
    properties.process_pair(IS_LDAP_CONFIGURED, 'true')
    get_ambari_properties_mock.return_value = properties
    get_validated_string_input_mock.side_effect = ['admin', 'admin']

    response = MagicMock()
    response.getcode.side_effect = [201, 200, 200]
    response.read.side_effect = ['{"resources" : [{"href" : "http://c6401.ambari.apache.org:8080/api/v1/ldap_sync_events/16","Event" : {"id" : 16}}]}',
                                 '{"Event":{"status" : "RUNNING","summary" : {"groups" : {"created" : 0,"removed" : 0,"updated" : 0},"memberships" : {"created" : 0,"removed" : 0},"users" : {"created" : 0,"removed" : 0,"updated" : 0}}}}',
                                 '{"Event":{"status" : "COMPLETE","summary" : {"groups" : {"created" : 1,"removed" : 0,"updated" : 0},"memberships" : {"created" : 5,"removed" : 0},"users" : {"created" : 5,"removed" : 0,"updated" : 0}}}}']

    urlopen_mock.return_value = response

    options = MagicMock()
    options.ldap_sync_all = False
    options.ldap_sync_existing = True
    options.ldap_sync_users = None
    options.ldap_sync_groups = None

    sync_ldap(options)

    self.assertTrue(response.getcode.called)
    self.assertTrue(response.read.called)
    pass

  @patch("urllib2.urlopen")
  @patch("ambari_server.setupSecurity.get_validated_string_input")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.is_server_runing")
  @patch("ambari_server.setupSecurity.is_root")
  def test_ldap_sync_no_sync_mode(self, is_root_method, is_server_runing_mock, get_ambari_properties_mock,
                     get_validated_string_input_mock, urlopen_mock):

    is_root_method.return_value = True
    is_server_runing_mock.return_value = (True, 0)
    properties = Properties()
    properties.process_pair(IS_LDAP_CONFIGURED, 'true')
    get_ambari_properties_mock.return_value = properties
    get_validated_string_input_mock.side_effect = ['admin', 'admin']

    response = MagicMock()
    response.getcode.side_effect = [201, 200, 200]
    response.read.side_effect = ['{"resources" : [{"href" : "http://c6401.ambari.apache.org:8080/api/v1/ldap_sync_events/16","Event" : {"id" : 16}}]}',
                                 '{"Event":{"status" : "RUNNING","summary" : {"groups" : {"created" : 0,"removed" : 0,"updated" : 0},"memberships" : {"created" : 0,"removed" : 0},"users" : {"created" : 0,"removed" : 0,"updated" : 0}}}}',
                                 '{"Event":{"status" : "COMPLETE","summary" : {"groups" : {"created" : 1,"removed" : 0,"updated" : 0},"memberships" : {"created" : 5,"removed" : 0},"users" : {"created" : 5,"removed" : 0,"updated" : 0}}}}']

    urlopen_mock.return_value = response

    options = MagicMock()
    del options.ldap_sync_all
    del options.ldap_sync_existing
    del options.ldap_sync_users
    del options.ldap_sync_groups

    try:
      sync_ldap(options)
      self.fail("Should fail with exception")
    except FatalException as e:
      pass
    pass

  @patch("urllib2.urlopen")
  @patch("ambari_server.setupSecurity.get_validated_string_input")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.is_server_runing")
  @patch("ambari_server.setupSecurity.is_root")
  def test_ldap_sync_error_status(self, is_root_method, is_server_runing_mock, get_ambari_properties_mock,
      get_validated_string_input_mock, urlopen_mock):

    is_root_method.return_value = True
    is_server_runing_mock.return_value = (True, 0)
    properties = Properties()
    properties.process_pair(IS_LDAP_CONFIGURED, 'true')
    get_ambari_properties_mock.return_value = properties
    get_validated_string_input_mock.side_effect = ['admin', 'admin']

    response = MagicMock()
    response.getcode.side_effect = [201, 200]
    response.read.side_effect = ['{"resources" : [{"href" : "http://c6401.ambari.apache.org:8080/api/v1/ldap_sync_events/16","Event" : {"id" : 16}}]}',
                          '{"Event":{"status" : "ERROR","status_detail" : "Error!!","summary" : {"groups" : {"created" : 0,"removed" : 0,"updated" : 0},"memberships" : {"created" : 0,"removed" : 0},"users" : {"created" : 0,"removed" : 0,"updated" : 0}}}}']

    urlopen_mock.return_value = response

    options = MagicMock()
    options.ldap_sync_all = False
    options.ldap_sync_existing = False
    options.ldap_sync_users = None
    options.ldap_sync_groups = None

    try:
      sync_ldap(options)
      self.fail("Should fail with exception")
    except FatalException as e:
      pass
    pass

  @patch("urllib2.urlopen")
  @patch("urllib2.Request")
  @patch("base64.encodestring")
  @patch("ambari_server.setupSecurity.is_root")
  @patch("ambari_server.setupSecurity.is_server_runing")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  @patch("ambari_server.setupSecurity.get_validated_string_input")
  def test_sync_ldap_forbidden(self, get_validated_string_input_method, get_ambari_properties_method,
                                is_server_runing_method, is_root_method,
                                encodestring_method, request_constructor, urlopen_method):

    options = MagicMock()
    options.ldap_sync_all = True
    options.ldap_sync_existing = False
    options.ldap_sync_users = None
    options.ldap_sync_groups = None

    is_root_method.return_value = False
    try:
      sync_ldap(options)
      self.fail("Should throw exception if not root")
    except FatalException as fe:
      # Expected
      self.assertTrue("root-level" in fe.reason)
      pass
    is_root_method.return_value = True

    is_server_runing_method.return_value = (None, None)
    try:
      sync_ldap(options)
      self.fail("Should throw exception if ambari is stopped")
    except FatalException as fe:
      # Expected
      self.assertTrue("not running" in fe.reason)
      pass
    is_server_runing_method.return_value = (True, None)

    configs = MagicMock()
    configs.get_property.return_value = None
    get_ambari_properties_method.return_value = configs
    try:
      sync_ldap(options)
      self.fail("Should throw exception if ldap is not configured")
    except FatalException as fe:
      # Expected
      self.assertTrue("not configured" in fe.reason)
      pass
    configs.get_property.return_value = 'true'

    get_validated_string_input_method.return_value = 'admin'
    encodestring_method.return_value = 'qwe123'

    requestMocks = [MagicMock()]
    request_constructor.side_effect = requestMocks
    response = MagicMock()
    response.getcode.return_value = 403
    urlopen_method.return_value = response

    try:
      sync_ldap(options)
      self.fail("Should throw exception if return code != 200")
    except FatalException as fe:
      # Expected
      self.assertTrue("status code" in fe.reason)
      pass
    pass

  @patch("ambari_server.setupSecurity.is_root")
  def test_sync_ldap_ambari_stopped(self, is_root_method):
    is_root_method.return_value = False

    options = MagicMock()
    options.ldap_sync_all = True
    options.ldap_sync_existing = False
    options.ldap_sync_users = None
    options.ldap_sync_groups = None

    try:
      sync_ldap(options)
      self.fail("Should throw exception if not root")
    except FatalException as fe:
      # Expected
      self.assertTrue("root-level" in fe.reason)
      pass
    pass

  @patch("ambari_server.setupSecurity.is_root")
  @patch("ambari_server.setupSecurity.is_server_runing")
  def test_sync_ldap_ambari_stopped(self, is_server_runing_method, is_root_method):
    is_root_method.return_value = True
    is_server_runing_method.return_value = (None, None)

    options = MagicMock()
    options.ldap_sync_all = True
    options.ldap_sync_existing = False
    options.ldap_sync_users = None
    options.ldap_sync_groups = None

    try:
      sync_ldap(options)
      self.fail("Should throw exception if ambari is stopped")
    except FatalException as fe:
      # Expected
      self.assertTrue("not running" in fe.reason)
      pass
    pass

  @patch("ambari_server.setupSecurity.is_root")
  @patch("ambari_server.setupSecurity.is_server_runing")
  @patch("ambari_server.setupSecurity.get_ambari_properties")
  def test_sync_ldap_not_configured(self, get_ambari_properties_method,
                     is_server_runing_method, is_root_method):
    is_root_method.return_value = True
    is_server_runing_method.return_value = (True, None)

    configs = MagicMock()
    configs.get_property.return_value = None
    get_ambari_properties_method.return_value = configs

    options = MagicMock()
    options.ldap_sync_all = True
    del options.ldap_sync_existing
    del options.ldap_sync_users
    del options.ldap_sync_groups

    try:
      sync_ldap(options)
      self.fail("Should throw exception if ldap is not configured")
    except FatalException as fe:
      # Expected
      self.assertTrue("not configured" in fe.reason)
      pass
    pass

  @patch("__builtin__.open")
  @patch("os.path.exists")
  def test_get_ldap_event_spec_names(self, os_path_exists_mock, open_mock):
    os_path_exists_mock.return_value = 1
    f = MagicMock()
    f.__enter__().read.return_value = "\n\n\t some group, \tanother group, \n\t\tgrp, \ngroup*\n\n\n\n"

    open_mock.return_value = f

    bodies = [{"Event":{"specs":[]}}]
    body = bodies[0]
    events = body['Event']
    specs = events['specs']

    new_specs = [{"principal_type":"groups","sync_type":"specific","names":""}]

    get_ldap_event_spec_names("groups.txt", specs, new_specs)

    self.assertEquals("[{'Event': {'specs': [{'principal_type': 'groups', 'sync_type': 'specific', 'names': ' some group, another group, grp, group*'}]}}]", str(bodies))
    pass

  @patch("ambari_server.setupSecurity.read_password")
  def test_configure_ldap_password(self, read_password_method):
    out = StringIO.StringIO()
    sys.stdout = out
    read_password_method.return_value = "blah"

    configure_ldap_password()

    self.assertTrue(read_password_method.called)

    sys.stdout = sys.__stdout__
    pass

  @patch("ambari_server.userInput.get_validated_string_input")
  def test_read_password(self, get_validated_string_input_method):
    out = StringIO.StringIO()
    sys.stdout = out

    passwordDefault = ""
    passwordPrompt = 'Enter Manager Password* : '
    passwordPattern = ".*"
    passwordDescr = "Invalid characters in password."

    get_validated_string_input_method.side_effect = ['', 'aaa', 'aaa']
    password = read_password(passwordDefault, passwordPattern,
                                           passwordPrompt, passwordDescr)
    self.assertTrue(3, get_validated_string_input_method.call_count)
    self.assertEquals('aaa', password)

    get_validated_string_input_method.reset_mock()
    get_validated_string_input_method.side_effect = ['aaa', 'aaa']
    password = read_password(passwordDefault, passwordPattern,
                                           passwordPrompt, passwordDescr)
    self.assertTrue(2, get_validated_string_input_method.call_count)
    self.assertEquals('aaa', password)

    get_validated_string_input_method.reset_mock()
    get_validated_string_input_method.side_effect = ['aaa']
    password = read_password('aaa', passwordPattern,
                                           passwordPrompt, passwordDescr)
    self.assertTrue(1, get_validated_string_input_method.call_count)
    self.assertEquals('aaa', password)

    sys.stdout = sys.__stdout__
    pass

  def test_generate_random_string(self):
    random_str_len = 100
    str1 = generate_random_string(random_str_len)
    self.assertTrue(len(str1) == random_str_len)

    str2 = generate_random_string(random_str_len)
    self.assertTrue(str1 != str2)
    pass

  @patch("__builtin__.open")
  @patch("ambari_server.serverConfiguration.search_file")
  @patch("ambari_server.serverConfiguration.backup_file_in_temp")
  def test_update_properties_2(self, backup_file_in_temp_mock, search_file_mock, open_mock):
    conf_file = "ambari.properties"
    propertyMap = {"1": "1", "2": "2"}
    properties = MagicMock()
    f = MagicMock(name="file")
    # f.__enter__.return_value = f #mimic file behavior
    search_file_mock.return_value = conf_file
    open_mock.return_value = f

    update_properties_2(properties, propertyMap)

    properties.store_ordered.assert_called_with(f.__enter__.return_value)
    backup_file_in_temp_mock.assert_called_with(conf_file)
    self.assertEquals(2, properties.removeOldProp.call_count)
    self.assertEquals(2, properties.process_pair.call_count)

    properties = MagicMock()
    backup_file_in_temp_mock.reset_mock()
    open_mock.reset_mock()

    update_properties_2(properties, None)
    properties.store_ordered.assert_called_with(f.__enter__.return_value)
    backup_file_in_temp_mock.assert_called_with(conf_file)
    self.assertFalse(properties.removeOldProp.called)
    self.assertFalse(properties.process_pair.called)

    pass


  def test_regexps(self):
    res = re.search(REGEX_HOSTNAME_PORT, "")
    self.assertTrue(res is None)
    res = re.search(REGEX_HOSTNAME_PORT, "ddd")
    self.assertTrue(res is None)
    res = re.search(REGEX_HOSTNAME_PORT, "gg:ff")
    self.assertTrue(res is None)
    res = re.search(REGEX_HOSTNAME_PORT, "gg:55444325")
    self.assertTrue(res is None)
    res = re.search(REGEX_HOSTNAME_PORT, "gg:555")
    self.assertTrue(res is not None)

    res = re.search(REGEX_TRUE_FALSE, "")
    self.assertTrue(res is not None)
    res = re.search(REGEX_TRUE_FALSE, "t")
    self.assertTrue(res is None)
    res = re.search(REGEX_TRUE_FALSE, "trrrr")
    self.assertTrue(res is None)
    res = re.search(REGEX_TRUE_FALSE, "true|false")
    self.assertTrue(res is None)
    res = re.search(REGEX_TRUE_FALSE, "true")
    self.assertTrue(res is not None)
    res = re.search(REGEX_TRUE_FALSE, "false")
    self.assertTrue(res is not None)

    res = re.search(REGEX_ANYTHING, "")
    self.assertTrue(res is not None)
    res = re.search(REGEX_ANYTHING, "t")
    self.assertTrue(res is not None)
    res = re.search(REGEX_ANYTHING, "trrrr")
    self.assertTrue(res is not None)
    pass


  def get_sample(self, sample):
    """
    Returns sample file content as string with normalized line endings
    """
    path = self.get_samples_dir(sample)
    return self.get_file_string(path)

  def get_file_string(self, file):
    """
    Returns file content as string with normalized line endings
    """
    string = open(file, 'r').read()
    return self.normalize(string)


  def normalize(self, string):
    """
    Normalizes line ending in string according to platform-default encoding
    """
    return string.replace("\n", os.linesep)


  def get_samples_dir(self, sample):
    """
    Returns full file path by sample name
    """
    testdir = os.path.dirname(__file__)
    return os.path.dirname(testdir) + os.sep + "resources" + os.sep \
           + 'TestAmbaryServer.samples/' + sample


  @not_for_platform(PLATFORM_WINDOWS)
  @patch("ambari_server.dbConfiguration_linux.get_ambari_properties")
  def test_is_jdbc_user_changed(self, get_ambari_properties_mock):
    previous_user = "previous_user"
    new_user = "new_user"

    props = Properties()
    props.process_pair(JDBC_USER_NAME_PROPERTY, previous_user)
    get_ambari_properties_mock.return_value = props

    #check if users are different
    result = PGConfig._is_jdbc_user_changed(new_user)
    self.assertTrue(result)

    #check if users are equal
    result = PGConfig._is_jdbc_user_changed(previous_user)
    self.assertFalse(result)

    #check if one of users is None
    result = PGConfig._is_jdbc_user_changed(None)
    self.assertEqual(None, result)
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch("ambari_server.serverConfiguration.write_property")
  @patch("ambari_server.serverConfiguration.get_ambari_properties")
  @patch("ambari_server.serverConfiguration.get_ambari_version")
  def test_check_database_name_property(self, get_ambari_version_mock, get_ambari_properties_mock, write_property_mock):
    parser = OptionParser()
    parser.add_option('--database', default=None, help="Database to use embedded|oracle|mysql|mssql|postgres", dest="dbms")
    args = parser.parse_args()

    # negative case
    get_ambari_properties_mock.return_value = {JDBC_DATABASE_NAME_PROPERTY: ""}
    try:
      result = check_database_name_property()
      self.fail("Should fail with exception")
    except FatalException as e:
      self.assertTrue('DB Name property not set in config file.' in e.reason)

    # positive case
    dbname = "ambari"
    get_ambari_properties_mock.reset_mock()
    get_ambari_properties_mock.return_value = {JDBC_DATABASE_NAME_PROPERTY: dbname}
    try:
      result = check_database_name_property()
    except FatalException:
      self.fail("Setup should be successful")

    # Check upgrade. In Ambari < 1.7.1 "database" property contained db name for local db
    dbname = "ambari"
    database = "ambari"
    persistence = "local"
    get_ambari_properties_mock.reset_mock()
    get_ambari_properties_mock.return_value = {JDBC_DATABASE_NAME_PROPERTY: dbname,
                                               JDBC_DATABASE_PROPERTY: database,
                                               PERSISTENCE_TYPE_PROPERTY: persistence}
    try:
      result = check_database_name_property(upgrade=True)
    except FatalException:
      self.fail("Setup should be successful")
    self.assertTrue(write_property_mock.called)

  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_commons.firewall.run_os_command")
  @patch("ambari_server.dbConfiguration_linux.PGConfig._is_jdbc_user_changed")
  @patch("ambari_server.serverSetup.verify_setup_allowed")
  @patch("ambari_server.serverSetup.get_YN_input")
  @patch("ambari_server.serverSetup.configure_os_settings")
  @patch("ambari_server.serverSetup.download_and_install_jdk")
  @patch.object(PGConfig, "_configure_postgres")
  @patch.object(PGConfig, "_check_postgre_up")
  @patch("ambari_server.serverSetup.check_ambari_user")
  @patch("ambari_server.serverSetup.check_jdbc_drivers")
  @patch("ambari_server.serverSetup.check_selinux")
  @patch("ambari_server.serverSetup.is_root")
  @patch.object(PGConfig, "_setup_db")
  @patch("ambari_server.serverSetup.get_is_secure")
  @patch("ambari_server.dbConfiguration_linux.store_password_file")
  @patch("ambari_server.serverSetup.extract_views")
  @patch("ambari_server.serverSetup.adjust_directory_permissions")
  @patch("sys.exit")
  @patch("__builtin__.raw_input")
  @patch("ambari_server.serverSetup.expand_jce_zip_file")
  def test_ambariServerSetupWithCustomDbName(self, expand_jce_zip_file_mock, raw_input, exit_mock, adjust_dirs_mock,
                                             extract_views_mock, store_password_file_mock,
                                             get_is_secure_mock, setup_db_mock, is_root_mock, #is_local_database_mock,
                                             check_selinux_mock, check_jdbc_drivers_mock, check_ambari_user_mock,
                                             check_postgre_up_mock, configure_postgres_mock,
                                             download_jdk_mock, configure_os_settings_mock, get_YN_input,
                                             verify_setup_allowed_method, is_jdbc_user_changed_mock,
                                             run_os_command_mock):

    args = MagicMock()

    raw_input.return_value = ""
    get_YN_input.return_value = False
    verify_setup_allowed_method.return_value = 0
    is_root_mock.return_value = True
    check_selinux_mock.return_value = 0
    check_ambari_user_mock.return_value = (0, False, 'user', None)
    check_jdbc_drivers_mock.return_value = 0
    check_postgre_up_mock.return_value = "running", 0, "", ""
    #is_local_database_mock.return_value = True
    configure_postgres_mock.return_value = 0, "", ""
    download_jdk_mock.return_value = 0
    configure_os_settings_mock.return_value = 0
    is_jdbc_user_changed_mock.return_value = False
    setup_db_mock.return_value = (0, None, None)
    get_is_secure_mock.return_value = False
    store_password_file_mock.return_value = "password"
    extract_views_mock.return_value = 0
    run_os_command_mock.return_value = 3,"",""

    new_db = "newDBName"
    args.dbms = "postgres"
    args.database_name = new_db
    args.postgres_schema = new_db
    args.database_username = "user"
    args.database_password = "password"
    args.jdbc_driver= None
    args.jdbc_db = None
    args.must_set_database_options = True

    del args.database_index
    del args.persistence_type

    tempdir = tempfile.gettempdir()
    prop_file = os.path.join(tempdir, "ambari.properties")
    with open(prop_file, "w") as f:
      f.write("server.jdbc.database_name=oldDBName")
    f.close()

    os.environ[AMBARI_CONF_VAR] = tempdir

    try:
      result = setup(args)
    except FatalException as ex:
      self.fail("Setup should be successful")

    properties = get_ambari_properties()

    self.assertTrue(JDBC_DATABASE_NAME_PROPERTY in properties.keys())
    value = properties[JDBC_DATABASE_NAME_PROPERTY]
    self.assertEqual(value, new_db)

    del os.environ[AMBARI_CONF_VAR]
    os.remove(prop_file)
    pass


  def test_is_valid_filepath(self):
    temp_dir = tempfile.gettempdir()
    temp_file = tempfile.NamedTemporaryFile(mode='r')

    # Correct path to an existing file
    self.assertTrue(temp_file)
    # Correct path to an existing directory
    self.assertFalse(is_valid_filepath(temp_dir), \
      'is_valid_filepath(path) should return False is path is a directory')
    # Incorrect path
    self.assertFalse(is_valid_filepath(''))
    pass

  @patch("ambari_server.setupSecurity.search_file")
  @patch("ambari_server.setupSecurity.get_validated_string_input")
  def test_setup_ambari_krb5_jaas(self, get_validated_string_input_mock,
                                  search_file_mock):
    search_file_mock.return_value = ''

    # Should raise exception if jaas_conf_file isn't an existing file
    self.assertRaises(NonFatalException, setup_ambari_krb5_jaas)

    temp_file = tempfile.NamedTemporaryFile(mode='r')
    search_file_mock.return_value = temp_file.name
    get_validated_string_input_mock.side_effect = ['adm@EXAMPLE.COM', temp_file]

    # setup_ambari_krb5_jaas() should return None if everything is OK
    self.assertEqual(None, setup_ambari_krb5_jaas())
    self.assertTrue(get_validated_string_input_mock.called)
    self.assertEqual(get_validated_string_input_mock.call_count, 2)
    pass

  @patch("os.listdir")
  @patch("os.path.exists")
  @patch("ambari_server.serverUpgrade.load_stack_values")
  @patch("ambari_server.serverUpgrade.get_ambari_properties")
  @patch("ambari_server.serverUpgrade.run_metainfo_upgrade")
  def test_upgrade_local_repo(self,
                           run_metainfo_upgrade_mock,
                           get_ambari_properties_mock,
                           load_stack_values_mock,
                           os_path_exists_mock,
                           os_listdir_mock):

    from mock.mock import call
    args = MagicMock()
    args.persistence_type = "local"

    def load_values_side_effect(*args, **kwargs):
      res = {}
      res['a'] = 'http://oldurl'
      if -1 != args[1].find("HDPLocal"):
        res['a'] = 'http://newurl'
      return res

    load_stack_values_mock.side_effect = load_values_side_effect

    properties = Properties()
    get_ambari_properties_mock.return_value = properties
    os_path_exists_mock.return_value = 1
    os_listdir_mock.return_value = ['1.1']

    upgrade_local_repo(args)

    self.assertTrue(get_ambari_properties_mock.called)
    self.assertTrue(load_stack_values_mock.called)
    self.assertTrue(run_metainfo_upgrade_mock.called)
    run_metainfo_upgrade_mock.assert_called_with({'a': 'http://newurl'})
    pass

  @patch("os.listdir")
  @patch("os.path.exists")
  @patch("ambari_server.serverUpgrade.load_stack_values")
  @patch("ambari_server.serverUpgrade.get_ambari_properties")
  @patch("ambari_server.serverUpgrade.run_metainfo_upgrade")
  def test_upgrade_local_repo_nochange(self,
                         run_metainfo_upgrade_mock,
                         get_ambari_properties_mock,
                         load_stack_values_mock,
                         os_path_exists_mock,
                         os_listdir_mock):

    from mock.mock import call
    args = MagicMock()
    args.persistence_type = "local"

    def load_values_side_effect(*args, **kwargs):
      res = {}
      res['a'] = 'http://oldurl'
      return res

    load_stack_values_mock.side_effect = load_values_side_effect

    properties = Properties()
    get_ambari_properties_mock.return_value = properties
    os_path_exists_mock.return_value = 1
    os_listdir_mock.return_value = ['1.1']

    upgrade_local_repo(args)

    self.assertTrue(get_ambari_properties_mock.called)
    self.assertTrue(load_stack_values_mock.called)
    self.assertTrue(run_metainfo_upgrade_mock.called)
    run_metainfo_upgrade_mock.assert_called_with({})
    pass

  @patch("os.path.exists")
  @patch.object(ResourceFilesKeeper, "perform_housekeeping")
  def test_refresh_stack_hash(self,
    perform_housekeeping_mock, path_exists_mock):

    path_exists_mock.return_value = True

    properties = Properties()
    refresh_stack_hash(properties)

    self.assertTrue(perform_housekeeping_mock.called)
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  @patch("ambari_server.dbConfiguration_linux.print_error_msg")
  def test_change_objects_owner_both(self,
                                     print_error_msg_mock,
                                     run_os_command_mock):
    args = MagicMock()
    args.master_key = None

    del args.database_index
    del args.dbms
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password
    del args.persistence_type

    stdout = " stdout "
    stderr = " stderr "
    run_os_command_mock.return_value = 1, stdout, stderr

    set_verbose(True)
    self.assertRaises(FatalException, change_objects_owner, args)
    print_error_msg_mock.assert_any_call("stderr:\nstderr")
    print_error_msg_mock.assert_any_call("stdout:\nstdout")
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  @patch("ambari_server.dbConfiguration_linux.print_error_msg")
  def test_change_objects_owner_only_stdout(self,
                                            print_error_msg_mock,
                                            run_os_command_mock):
    args = MagicMock()

    del args.database_index
    del args.dbms
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password
    del args.persistence_type

    stdout = " stdout "
    stderr = ""
    run_os_command_mock.return_value = 1, stdout, stderr

    set_verbose(True)
    self.assertRaises(FatalException, change_objects_owner, args)
    print_error_msg_mock.assert_called_once_with("stdout:\nstdout")
    pass

  @not_for_platform(PLATFORM_WINDOWS)
  @patch.object(OSCheck, "os_distribution", new = MagicMock(return_value = os_distro_value))
  @patch("ambari_server.dbConfiguration_linux.run_os_command")
  @patch("ambari_server.dbConfiguration_linux.print_error_msg")
  def test_change_objects_owner_only_stderr(self,
                                            print_error_msg_mock,
                                            run_os_command_mock):
    args = MagicMock()

    del args.database_index
    del args.dbms
    del args.database_host
    del args.database_port
    del args.database_name
    del args.database_username
    del args.database_password
    del args.persistence_type

    stdout = ""
    stderr = " stderr "
    run_os_command_mock.return_value = 1, stdout, stderr

    set_verbose(True)
    self.assertRaises(FatalException, change_objects_owner, args)
    print_error_msg_mock.assert_called_once_with("stderr:\nstderr")
    pass
