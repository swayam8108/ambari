#!/usr/bin/env ambari-python-wrap
"""
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
"""

import math
from math import floor
from urlparse import urlparse

class HDP22StackAdvisor(HDP21StackAdvisor):

  def getServiceConfigurationRecommenderDict(self):
    parentRecommendConfDict = super(HDP22StackAdvisor, self).getServiceConfigurationRecommenderDict()
    childRecommendConfDict = {
      "HDFS": self.recommendHDFSConfigurations,
      "HIVE": self.recommendHIVEConfigurations,
      "HBASE": self.recommendHBASEConfigurations,
      "MAPREDUCE2": self.recommendMapReduce2Configurations,
      "TEZ": self.recommendTezConfigurations,
      "AMBARI_METRICS": self.recommendAmsConfigurations,
      "YARN": self.recommendYARNConfigurations
    }
    parentRecommendConfDict.update(childRecommendConfDict)
    return parentRecommendConfDict

  def recommendYARNConfigurations(self, configurations, clusterData, services, hosts):
    super(HDP22StackAdvisor, self).recommendYARNConfigurations(configurations, clusterData, services, hosts)
    putYarnProperty = self.putProperty(configurations, "yarn-site", services)
    putYarnProperty('yarn.nodemanager.resource.cpu-vcores', clusterData['cpu'])
    putYarnProperty('yarn.scheduler.minimum-allocation-vcores', 1)
    putYarnProperty('yarn.scheduler.maximum-allocation-vcores', configurations["yarn-site"]["properties"]["yarn.nodemanager.resource.cpu-vcores"])
    # Property Attributes
    putYarnPropertyAttribute = self.putPropertyAttribute(configurations, "yarn-site")
    nodeManagerHost = self.getHostWithComponent("YARN", "NODEMANAGER", services, hosts)
    if (nodeManagerHost is not None):
      cpuPercentageLimit = 0.8
      if "yarn.nodemanager.resource.percentage-physical-cpu-limit" in configurations["yarn-site"]["properties"]:
        cpuPercentageLimit = float(configurations["yarn-site"]["properties"]["yarn.nodemanager.resource.percentage-physical-cpu-limit"])
      cpuLimit = max(1, int(floor(nodeManagerHost["Hosts"]["cpu_count"] * cpuPercentageLimit)))
      putYarnProperty('yarn.nodemanager.resource.cpu-vcores', str(cpuLimit))
      putYarnProperty('yarn.scheduler.maximum-allocation-vcores', configurations["yarn-site"]["properties"]["yarn.nodemanager.resource.cpu-vcores"])
      putYarnPropertyAttribute('yarn.nodemanager.resource.memory-mb', 'maximum', int(nodeManagerHost["Hosts"]["total_mem"] / 1024)) # total_mem in kb
      putYarnPropertyAttribute('yarn.nodemanager.resource.cpu-vcores', 'maximum', nodeManagerHost["Hosts"]["cpu_count"] * 2)
      putYarnPropertyAttribute('yarn.scheduler.minimum-allocation-vcores', 'maximum', configurations["yarn-site"]["properties"]["yarn.nodemanager.resource.cpu-vcores"])
      putYarnPropertyAttribute('yarn.scheduler.maximum-allocation-vcores', 'maximum', configurations["yarn-site"]["properties"]["yarn.nodemanager.resource.cpu-vcores"])
      putYarnPropertyAttribute('yarn.scheduler.minimum-allocation-mb', 'maximum', configurations["yarn-site"]["properties"]["yarn.nodemanager.resource.memory-mb"])
      putYarnPropertyAttribute('yarn.scheduler.maximum-allocation-mb', 'maximum', configurations["yarn-site"]["properties"]["yarn.nodemanager.resource.memory-mb"])
      # Above is the default calculated 'maximum' values derived purely from hosts.
      # However, there are 'maximum' and other attributes that actually change based on the values
      #  of other configs. We need to update those values.
      if ("yarn-site" in services["configurations"]):
        if ("yarn.nodemanager.resource.memory-mb" in services["configurations"]["yarn-site"]["properties"]):
          putYarnPropertyAttribute('yarn.scheduler.maximum-allocation-mb', 'maximum', services["configurations"]["yarn-site"]["properties"]["yarn.nodemanager.resource.memory-mb"])
          putYarnPropertyAttribute('yarn.scheduler.minimum-allocation-mb', 'maximum', services["configurations"]["yarn-site"]["properties"]["yarn.nodemanager.resource.memory-mb"])
        if ("yarn.nodemanager.resource.cpu-vcores" in services["configurations"]["yarn-site"]["properties"]):
          putYarnPropertyAttribute('yarn.scheduler.maximum-allocation-vcores', 'maximum', services["configurations"]["yarn-site"]["properties"]["yarn.nodemanager.resource.cpu-vcores"])
          putYarnPropertyAttribute('yarn.scheduler.minimum-allocation-vcores', 'maximum', services["configurations"]["yarn-site"]["properties"]["yarn.nodemanager.resource.cpu-vcores"])

      if "yarn-env" in services["configurations"] and "yarn_cgroups_enabled" in services["configurations"]["yarn-env"]["properties"]:
        yarn_cgroups_enabled = services["configurations"]["yarn-env"]["properties"]["yarn_cgroups_enabled"].lower() == "true"
        if yarn_cgroups_enabled:
          putYarnProperty('yarn.nodemanager.container-executor.class', 'org.apache.hadoop.yarn.server.nodemanager.LinuxContainerExecutor')
          putYarnProperty('yarn.nodemanager.container-executor.group', 'hadoop')
          putYarnProperty('yarn.nodemanager.container-executor.resources-handler.class', 'org.apache.hadoop.yarn.server.nodemanager.util.CgroupsLCEResourcesHandler')
          putYarnProperty('yarn.nodemanager.container-executor.cgroups.hierarchy', ' /yarn')
          putYarnProperty('yarn.nodemanager.container-executor.cgroups.mount', 'true')
          putYarnProperty('yarn.nodemanager.linux-container-executor.cgroups.mount-path', '/cgroup')
        else:
          putYarnProperty('yarn.nodemanager.container-executor.class', 'org.apache.hadoop.yarn.server.nodemanager.DefaultContainerExecutor')
          putYarnPropertyAttribute('yarn.nodemanager.container-executor.resources-handler.class', 'delete', 'true')
          putYarnPropertyAttribute('yarn.nodemanager.container-executor.cgroups.hierarchy', 'delete', 'true')
          putYarnPropertyAttribute('yarn.nodemanager.container-executor.cgroups.mount', 'delete', 'true')
          putYarnPropertyAttribute('yarn.nodemanager.linux-container-executor.cgroups.mount-path', 'delete', 'true')

  def recommendHDFSConfigurations(self, configurations, clusterData, services, hosts):
    putHdfsSiteProperty = self.putProperty(configurations, "hdfs-site", services)
    putHdfsSitePropertyAttribute = self.putPropertyAttribute(configurations, "hdfs-site")
    putHdfsSiteProperty("dfs.datanode.max.transfer.threads", 16384 if clusterData["hBaseInstalled"] else 4096)

    dataDirsCount = 1
    # Use users 'dfs.datanode.data.dir' first
    if "hdfs-site" in services["configurations"] and "dfs.datanode.data.dir" in services["configurations"]["hdfs-site"]["properties"]:
      dataDirsCount = len(str(services["configurations"]["hdfs-site"]["properties"]["dfs.datanode.data.dir"]).split(","))
    elif "dfs.datanode.data.dir" in configurations["hdfs-site"]["properties"]:
      dataDirsCount = len(str(configurations["hdfs-site"]["properties"]["dfs.datanode.data.dir"]).split(","))
    if dataDirsCount <= 2:
      failedVolumesTolerated = 0
    elif dataDirsCount <= 4:
      failedVolumesTolerated = 1
    else:
      failedVolumesTolerated = 2
    putHdfsSiteProperty("dfs.datanode.failed.volumes.tolerated", failedVolumesTolerated)

    namenodeHosts = self.getHostsWithComponent("HDFS", "NAMENODE", services, hosts)

    # 25 * # of cores on NameNode
    nameNodeCores = 4
    if namenodeHosts is not None and len(namenodeHosts):
      nameNodeCores = int(namenodeHosts[0]['Hosts']['cpu_count'])
    putHdfsSiteProperty("dfs.namenode.handler.count", 25 * nameNodeCores)
    if 25 * nameNodeCores > 200:
      putHdfsSitePropertyAttribute("dfs.namenode.handler.count", "maximum", 25 * nameNodeCores)

    servicesList = [service["StackServices"]["service_name"] for service in services["services"]]
    if ('ranger-hdfs-plugin-properties' in services['configurations']) and ('ranger-hdfs-plugin-enabled' in services['configurations']['ranger-hdfs-plugin-properties']['properties']):
      rangerPluginEnabled = services['configurations']['ranger-hdfs-plugin-properties']['properties']['ranger-hdfs-plugin-enabled']
      if ("RANGER" in servicesList) and (rangerPluginEnabled.lower() == 'Yes'.lower()):
        putHdfsSiteProperty("dfs.permissions.enabled",'true')

    putHdfsSiteProperty("dfs.namenode.safemode.threshold-pct", "0.999" if len(namenodeHosts) > 1 else "1.000")

    putHdfsEnvProperty = self.putProperty(configurations, "hadoop-env", services)
    putHdfsEnvPropertyAttribute = self.putPropertyAttribute(configurations, "hadoop-env")

    putHdfsEnvProperty('namenode_heapsize', max(int(clusterData['totalAvailableRam'] / 2), 1024))

    nn_heapsize_limit = None
    if (namenodeHosts is not None and len(namenodeHosts) > 0):
      if len(namenodeHosts) > 1:
        nn_max_heapsize = min(int(namenodeHosts[0]["Hosts"]["total_mem"]), int(namenodeHosts[1]["Hosts"]["total_mem"])) / 1024
        masters_at_host = max(self.getHostComponentsByCategories(namenodeHosts[0]["Hosts"]["host_name"], ["MASTER"], services, hosts),
                              self.getHostComponentsByCategories(namenodeHosts[1]["Hosts"]["host_name"], ["MASTER"], services, hosts))
      else:
        nn_max_heapsize = int(namenodeHosts[0]["Hosts"]["total_mem"] / 1024) # total_mem in kb
        masters_at_host = self.getHostComponentsByCategories(namenodeHosts[0]["Hosts"]["host_name"], ["MASTER"], services, hosts)

      putHdfsEnvPropertyAttribute('namenode_heapsize', 'maximum', max(nn_max_heapsize, 1024))

      nn_heapsize_limit = nn_max_heapsize
      nn_heapsize_limit -= clusterData["reservedRam"]
      if len(masters_at_host) > 1:
        nn_heapsize_limit = int(nn_heapsize_limit/2)

      putHdfsEnvProperty('namenode_heapsize', max(nn_heapsize_limit, 1024))


    datanodeHosts = self.getHostsWithComponent("HDFS", "DATANODE", services, hosts)
    if datanodeHosts is not None and len(datanodeHosts) > 0:
      min_datanode_ram_kb = 1073741824 # 1 TB
      for datanode in datanodeHosts:
        ram_kb = datanode['Hosts']['total_mem']
        min_datanode_ram_kb = min(min_datanode_ram_kb, ram_kb)

      datanodeFilesM = len(datanodeHosts)*dataDirsCount/10 # in millions, # of files = # of disks * 100'000
      nn_memory_configs = [
        {'nn_heap':1024,  'nn_opt':128},
        {'nn_heap':3072,  'nn_opt':512},
        {'nn_heap':5376,  'nn_opt':768},
        {'nn_heap':9984,  'nn_opt':1280},
        {'nn_heap':14848, 'nn_opt':2048},
        {'nn_heap':19456, 'nn_opt':2560},
        {'nn_heap':24320, 'nn_opt':3072},
        {'nn_heap':33536, 'nn_opt':4352},
        {'nn_heap':47872, 'nn_opt':6144},
        {'nn_heap':59648, 'nn_opt':7680},
        {'nn_heap':71424, 'nn_opt':8960},
        {'nn_heap':94976, 'nn_opt':8960}
      ]
      index = {
        datanodeFilesM < 1 : 0,
        1 <= datanodeFilesM < 5 : 1,
        5 <= datanodeFilesM < 10 : 2,
        10 <= datanodeFilesM < 20 : 3,
        20 <= datanodeFilesM < 30 : 4,
        30 <= datanodeFilesM < 40 : 5,
        40 <= datanodeFilesM < 50 : 6,
        50 <= datanodeFilesM < 70 : 7,
        70 <= datanodeFilesM < 100 : 8,
        100 <= datanodeFilesM < 125 : 9,
        125 <= datanodeFilesM < 150 : 10,
        150 <= datanodeFilesM : 11
      }[1]

      nn_memory_config = nn_memory_configs[index]

      #override with new values if applicable
      if nn_heapsize_limit is not None and nn_memory_config['nn_heap'] <= nn_heapsize_limit:
        putHdfsEnvProperty('namenode_heapsize', nn_memory_config['nn_heap'])

      putHdfsEnvPropertyAttribute('dtnode_heapsize', 'maximum', int(min_datanode_ram_kb/1024))

    nn_heapsize = int(configurations["hadoop-env"]["properties"]["namenode_heapsize"])
    putHdfsEnvProperty('namenode_opt_newsize', max(int(nn_heapsize / 8), 128))
    putHdfsEnvProperty('namenode_opt_maxnewsize', max(int(nn_heapsize / 8), 128))

    putHdfsSitePropertyAttribute = self.putPropertyAttribute(configurations, "hdfs-site")
    putHdfsSitePropertyAttribute('dfs.datanode.failed.volumes.tolerated', 'maximum', dataDirsCount)

    keyserverHostsString = None
    keyserverPortString = None
    if "hadoop-env" in services["configurations"] and "keyserver_host" in services["configurations"]["hadoop-env"]["properties"] and "keyserver_port" in services["configurations"]["hadoop-env"]["properties"]:
      keyserverHostsString = services["configurations"]["hadoop-env"]["properties"]["keyserver_host"]
      keyserverPortString = services["configurations"]["hadoop-env"]["properties"]["keyserver_port"]
    if keyserverHostsString is None or len(keyserverHostsString.strip()) < 1 :
      # Caller did not specify any value - so we recommend where they are installed
      rangerKMSServerHosts = self.getHostsWithComponent("RANGER_KMS", "RANGER_KMS_SERVER", services, hosts)
      if rangerKMSServerHosts is not None and len(rangerKMSServerHosts) > 0:
        rangerKMSServerHostsArray = []
        for rangeKMSServerHost in rangerKMSServerHosts:
          rangerKMSServerHostsArray.append(rangeKMSServerHost["Hosts"]["host_name"])
        keyserverHostsString = ",".join(rangerKMSServerHostsArray)
        if "kms-env" in services["configurations"] and "kms_port" in services["configurations"]["kms-env"]["properties"]:
          keyserverPortString = services["configurations"]["kms-env"]["properties"]["kms_port"]

    if keyserverHostsString is not None and len(keyserverHostsString.strip()) > 0:
      urlScheme = "http"
      if "ranger-kms-site" in services["configurations"] and \
          "ranger.service.https.attrib.ssl.enabled" in services["configurations"]["ranger-kms-site"]["properties"] and \
          services["configurations"]["ranger-kms-site"]["properties"]["ranger.service.https.attrib.ssl.enabled"].lower() == "true":
        urlScheme = "https"

      if keyserverPortString is None or len(keyserverPortString.strip()) < 1:
        keyserverPortString = ":9292"
      else:
        keyserverPortString = ":" + keyserverPortString.strip()
      putCoreSiteProperty = self.putProperty(configurations, "core-site", services)
      kmsPath = "kms://" + urlScheme + "@" + keyserverHostsString.strip() + keyserverPortString + "/kms"
      putCoreSiteProperty("hadoop.security.key.provider.path", kmsPath)
      putHdfsSiteProperty("dfs.encryption.key.provider.uri", kmsPath)

  def recommendHIVEConfigurations(self, configurations, clusterData, services, hosts):
    super(HDP22StackAdvisor, self).recommendHiveConfigurations(configurations, clusterData, services, hosts)

    putHiveServerProperty = self.putProperty(configurations, "hiveserver2-site", services)
    putHiveEnvProperty = self.putProperty(configurations, "hive-env", services)
    putHiveSiteProperty = self.putProperty(configurations, "hive-site", services)
    putHiveSitePropertyAttribute = self.putPropertyAttribute(configurations, "hive-site")

    servicesList = [service["StackServices"]["service_name"] for service in services["services"]]

    #  Storage
    putHiveEnvProperty("hive_exec_orc_storage_strategy", "SPEED")
    putHiveSiteProperty("hive.exec.orc.encoding.strategy", configurations["hive-env"]["properties"]["hive_exec_orc_storage_strategy"])
    putHiveSiteProperty("hive.exec.orc.compression.strategy", configurations["hive-env"]["properties"]["hive_exec_orc_storage_strategy"])

    putHiveSiteProperty("hive.exec.orc.default.stripe.size", "67108864")
    putHiveSiteProperty("hive.exec.orc.default.compress", "ZLIB")
    putHiveSiteProperty("hive.optimize.index.filter", "true")
    putHiveSiteProperty("hive.optimize.sort.dynamic.partition", "false")

    # Vectorization
    putHiveSiteProperty("hive.vectorized.execution.enabled", "true")
    putHiveSiteProperty("hive.vectorized.execution.reduce.enabled", "false")

    # Transactions
    putHiveEnvProperty("hive_txn_acid", "off")
    if str(configurations["hive-env"]["properties"]["hive_txn_acid"]).lower() == "on":
      putHiveSiteProperty("hive.txn.manager", "org.apache.hadoop.hive.ql.lockmgr.DbTxnManager")
      putHiveSiteProperty("hive.support.concurrency", "true")
      putHiveSiteProperty("hive.compactor.initiator.on", "true")
      putHiveSiteProperty("hive.compactor.worker.threads", "1")
      putHiveSiteProperty("hive.enforce.bucketing", "true")
      putHiveSiteProperty("hive.exec.dynamic.partition.mode", "nonstrict")
    else:
      putHiveSiteProperty("hive.txn.manager", "org.apache.hadoop.hive.ql.lockmgr.DummyTxnManager")
      putHiveSiteProperty("hive.support.concurrency", "false")
      putHiveSiteProperty("hive.compactor.initiator.on", "false")
      putHiveSiteProperty("hive.compactor.worker.threads", "0")
      putHiveSiteProperty("hive.enforce.bucketing", "false")
      putHiveSiteProperty("hive.exec.dynamic.partition.mode", "strict")

    # ATS
    putHiveEnvProperty("hive_timeline_logging_enabled", "true")

    hooks_properties = ["hive.exec.pre.hooks", "hive.exec.post.hooks", "hive.exec.failure.hooks"]
    include_ats_hook = str(configurations["hive-env"]["properties"]["hive_timeline_logging_enabled"]).lower() == "true"

    ats_hook_class = "org.apache.hadoop.hive.ql.hooks.ATSHook"
    for hooks_property in hooks_properties:
      if hooks_property in configurations["hive-site"]["properties"]:
        hooks_value = configurations["hive-site"]["properties"][hooks_property]
      else:
        hooks_value = " "
      if include_ats_hook and ats_hook_class not in hooks_value:
        if hooks_value == " ":
          hooks_value = ats_hook_class
        else:
          hooks_value = hooks_value + "," + ats_hook_class
      if not include_ats_hook and ats_hook_class in hooks_value:
        hooks_classes = []
        for hook_class in hooks_value.split(","):
          if hook_class != ats_hook_class and hook_class != " ":
            hooks_classes.append(hook_class)
        if hooks_classes:
          hooks_value = ",".join(hooks_classes)
        else:
          hooks_value = " "

      putHiveSiteProperty(hooks_property, hooks_value)

    # Tez Engine
    if "TEZ" in servicesList:
      putHiveSiteProperty("hive.execution.engine", "tez")
    else:
      putHiveSiteProperty("hive.execution.engine", "mr")

    container_size = "512"

    if not "yarn-site" in configurations:
      self.recommendYARNConfigurations(configurations, clusterData, services, hosts)
    #properties below should be always present as they are provided in HDP206 stack advisor at least
    yarnMaxAllocationSize = min(30 * int(configurations["yarn-site"]["properties"]["yarn.scheduler.minimum-allocation-mb"]), int(configurations["yarn-site"]["properties"]["yarn.scheduler.maximum-allocation-mb"]))
    #duplicate tez task resource calc logic, direct dependency doesn't look good here (in case of Hive without Tez)
    container_size = clusterData['mapMemory'] if clusterData['mapMemory'] > 2048 else int(clusterData['reduceMemory'])
    container_size = min(clusterData['containers'] * clusterData['ramPerContainer'], container_size, yarnMaxAllocationSize)

    putHiveSiteProperty("hive.tez.container.size", container_size)
    putHiveSiteProperty("hive.prewarm.enabled", "false")
    putHiveSiteProperty("hive.prewarm.numcontainers", "3")
    putHiveSiteProperty("hive.tez.auto.reducer.parallelism", "true")
    putHiveSiteProperty("hive.tez.dynamic.partition.pruning", "true")

    container_size = configurations["hive-site"]["properties"]["hive.tez.container.size"]
    container_size_bytes = int(container_size)*1024*1024
    # Memory
    putHiveSiteProperty("hive.auto.convert.join.noconditionaltask.size", int(round(container_size_bytes/3)))
    putHiveSitePropertyAttribute("hive.auto.convert.join.noconditionaltask.size", "maximum", container_size_bytes)
    putHiveSiteProperty("hive.exec.reducers.bytes.per.reducer", "67108864")

    # CBO
    putHiveEnvProperty("cost_based_optimizer", "On")
    if str(configurations["hive-env"]["properties"]["cost_based_optimizer"]).lower() == "on":
      putHiveSiteProperty("hive.cbo.enable", "true")
    else:
      putHiveSiteProperty("hive.cbo.enable", "false")
    hive_cbo_enable = configurations["hive-site"]["properties"]["hive.cbo.enable"]
    putHiveSiteProperty("hive.stats.fetch.partition.stats", hive_cbo_enable)
    putHiveSiteProperty("hive.stats.fetch.column.stats", hive_cbo_enable)
    putHiveSiteProperty("hive.compute.query.using.stats", "true")

    # Interactive Query
    putHiveSiteProperty("hive.server2.tez.initialize.default.sessions", "false")
    putHiveSiteProperty("hive.server2.tez.sessions.per.default.queue", "1")
    putHiveSiteProperty("hive.server2.enable.doAs", "true")

    yarn_queues = "default"
    capacitySchedulerProperties = services['configurations']["capacity-scheduler"]["properties"] if "capacity-scheduler" in services['configurations'] else {}
    if "yarn.scheduler.capacity.root.queues" in capacitySchedulerProperties:
      yarn_queues = str(capacitySchedulerProperties["yarn.scheduler.capacity.root.queues"])
    # Interactive Queues property attributes
    putHiveServerPropertyAttribute = self.putPropertyAttribute(configurations, "hiveserver2-site")
    toProcessQueues = yarn_queues.split(",")
    leafQueues = []
    while len(toProcessQueues) > 0:
      queue = toProcessQueues.pop();
      queueKey = "yarn.scheduler.capacity.root." + queue + ".queues"
      if queueKey in capacitySchedulerProperties:
        # This is a parent queue - need to add children
        subQueues = capacitySchedulerProperties[queueKey].split(",")
        for subQueue in subQueues:
          toProcessQueues.append(queue + "." + subQueue)
      else:
        # This is a leaf queue
        leafQueues.append({"label": str(queue) + " queue", "value": queue})
    leafQueues = sorted(leafQueues, key=lambda q:q['value'])
    putHiveSitePropertyAttribute("hive.server2.tez.default.queues", "entries", leafQueues)
    putHiveSiteProperty("hive.server2.tez.default.queues", ",".join([leafQueue['value'] for leafQueue in leafQueues]))

    # Security
    putHiveEnvProperty("hive_security_authorization", "None")
    # hive_security_authorization == 'none'
    # this property is unrelated to Kerberos
    if str(configurations["hive-env"]["properties"]["hive_security_authorization"]).lower() == "none":
      putHiveSiteProperty("hive.security.authorization.manager", "org.apache.hadoop.hive.ql.security.authorization.plugin.sqlstd.SQLStdConfOnlyAuthorizerFactory")
      putHiveServerPropertyAttribute("hive.security.authorization.manager", "delete", "true")
      putHiveServerPropertyAttribute("hive.security.authenticator.manager", "delete", "true")
      if "KERBEROS" not in servicesList: # Kerberos security depends on this property
        putHiveSiteProperty("hive.security.authorization.enabled", "false")
    else:
      putHiveSiteProperty("hive.security.authorization.enabled", "true")

    try:
      auth_manager_value = str(configurations["hive-env"]["properties"]["hive.security.metastore.authorization.manager"])
    except KeyError:
      auth_manager_value = 'org.apache.hadoop.hive.ql.security.authorization.StorageBasedAuthorizationProvider'
      pass
    auth_manager_values = auth_manager_value.split(",")
    sqlstdauth_class = "org.apache.hadoop.hive.ql.security.authorization.MetaStoreAuthzAPIAuthorizerEmbedOnly"

    putHiveSiteProperty("hive.server2.enable.doAs", "true")

    # hive_security_authorization == 'sqlstdauth'
    if str(configurations["hive-env"]["properties"]["hive_security_authorization"]).lower() == "sqlstdauth":
      putHiveSiteProperty("hive.server2.enable.doAs", "false")
      putHiveServerProperty("hive.security.authorization.enabled", "true")
      putHiveServerProperty("hive.security.authorization.manager", "org.apache.hadoop.hive.ql.security.authorization.plugin.sqlstd.SQLStdHiveAuthorizerFactory")
      putHiveServerProperty("hive.security.authenticator.manager", "org.apache.hadoop.hive.ql.security.SessionStateUserAuthenticator")
      putHiveSiteProperty("hive.security.authorization.manager", "org.apache.hadoop.hive.ql.security.authorization.plugin.sqlstd.SQLStdConfOnlyAuthorizerFactory")
      if sqlstdauth_class not in auth_manager_values:
        auth_manager_values.append(sqlstdauth_class)
    elif sqlstdauth_class in auth_manager_values:
      #remove item from csv
      auth_manager_values = [x for x in auth_manager_values if x != sqlstdauth_class]
      pass
    putHiveSiteProperty("hive.security.metastore.authorization.manager", ",".join(auth_manager_values))

    # hive_security_authorization == 'ranger'
    if str(configurations["hive-env"]["properties"]["hive_security_authorization"]).lower() == "ranger":
      putHiveSiteProperty("hive.server2.enable.doAs", "false")
      putHiveServerProperty("hive.security.authorization.enabled", "true")
      putHiveServerProperty("hive.security.authorization.manager", "com.xasecure.authorization.hive.authorizer.XaSecureHiveAuthorizerFactory")
      putHiveServerProperty("hive.security.authenticator.manager", "org.apache.hadoop.hive.ql.security.SessionStateUserAuthenticator")

    putHiveSiteProperty("hive.server2.use.SSL", "false")

    #Hive authentication
    hive_server2_auth = None
    if "hive-site" in services["configurations"] and "hive.server2.authentication" in services["configurations"]["hive-site"]["properties"]:
      hive_server2_auth = str(services["configurations"]["hive-site"]["properties"]["hive.server2.authentication"]).lower()
    elif "hive.server2.authentication" in configurations["hive-site"]["properties"]:
      hive_server2_auth = str(configurations["hive-site"]["properties"]["hive.server2.authentication"]).lower()

    if hive_server2_auth == "ldap":
      putHiveSiteProperty("hive.server2.authentication.ldap.url", "")
      putHiveSiteProperty("hive.server2.authentication.ldap.baseDN", " ")
    else:
      putHiveSitePropertyAttribute("hive.server2.authentication.ldap.url", "delete", "true")
      putHiveSitePropertyAttribute("hive.server2.authentication.ldap.baseDN", "delete", "true")

    if hive_server2_auth == "kerberos":
      putHiveSiteProperty("hive.server2.authentication.kerberos.keytab", "")
      putHiveSiteProperty("hive.server2.authentication.kerberos.principal", "")
    elif "KERBEROS" not in servicesList: # Since 'hive_server2_auth' cannot be relied on within the default, empty recommendations request
      putHiveSitePropertyAttribute("hive.server2.authentication.kerberos.keytab", "delete", "true")
      putHiveSitePropertyAttribute("hive.server2.authentication.kerberos.principal", "delete", "true")

    if hive_server2_auth == "pam":
      putHiveSiteProperty("hive.server2.authentication.pam.services", "")
    else:
      putHiveSitePropertyAttribute("hive.server2.authentication.pam.services", "delete", "true")

    if hive_server2_auth == "custom":
      putHiveSiteProperty("hive.server2.custom.authentication.class", "")
    else:
      putHiveSitePropertyAttribute("hive.server2.custom.authentication.class", "delete", "true")


  def recommendHBASEConfigurations(self, configurations, clusterData, services, hosts):
    super(HDP22StackAdvisor, self).recommendHbaseEnvConfigurations(configurations, clusterData, services, hosts)
    putHbaseEnvPropertyAttributes = self.putPropertyAttribute(configurations, "hbase-env")

    hmaster_host = self.getHostWithComponent("HBASE", "HBASE_MASTER", services, hosts)
    if hmaster_host is not None:
      host_ram = hmaster_host["Hosts"]["total_mem"]
      putHbaseEnvPropertyAttributes('hbase_master_heapsize', 'maximum', max(1024, int(host_ram/1024)))

    rs_hosts = self.getHostsWithComponent("HBASE", "HBASE_REGIONSERVER", services, hosts)
    if rs_hosts is not None and len(rs_hosts) > 0:
      min_ram = rs_hosts[0]["Hosts"]["total_mem"]
      for host in rs_hosts:
        host_ram = host["Hosts"]["total_mem"]
        min_ram = min(min_ram, host_ram)

      putHbaseEnvPropertyAttributes('hbase_regionserver_heapsize', 'maximum', max(1024, int(min_ram*0.8/1024)))

    putHbaseSiteProperty = self.putProperty(configurations, "hbase-site", services)
    putHbaseSitePropertyAttributes = self.putPropertyAttribute(configurations, "hbase-site")
    putHbaseSiteProperty("hbase.regionserver.global.memstore.size", '0.4')

    if 'hbase-env' in services['configurations'] and 'phoenix_sql_enabled' in services['configurations']['hbase-env']['properties']:
      if 'true' == services['configurations']['hbase-env']['properties']['phoenix_sql_enabled'].lower():
        putHbaseSiteProperty("hbase.regionserver.wal.codec", 'org.apache.hadoop.hbase.regionserver.wal.IndexedWALEditCodec')
        putHbaseSiteProperty("phoenix.functions.allowUserDefinedFunctions", 'true')
      else:
        putHbaseSiteProperty("hbase.regionserver.wal.codec", 'org.apache.hadoop.hbase.regionserver.wal.WALCellCodec')
        putHbaseSitePropertyAttributes('hbase.rpc.controllerfactory.class', 'delete', 'true')
        putHbaseSitePropertyAttributes('phoenix.functions.allowUserDefinedFunctions', 'delete', 'true')

    servicesList = [service["StackServices"]["service_name"] for service in services["services"]]
    if 'ranger-hbase-plugin-properties' in services['configurations'] and ('ranger-hbase-plugin-enabled' in services['configurations']['ranger-hbase-plugin-properties']['properties']):
      rangerPluginEnabled = services['configurations']['ranger-hbase-plugin-properties']['properties']['ranger-hbase-plugin-enabled']
      if ("RANGER" in servicesList) and (rangerPluginEnabled.lower() == "Yes".lower()):
        putHbaseSiteProperty("hbase.security.authorization", 'true')
        putHbaseSiteProperty("hbase.coprocessor.master.classes", 'com.xasecure.authorization.hbase.XaSecureAuthorizationCoprocessor')
        putHbaseSiteProperty("hbase.coprocessor.region.classes", 'com.xasecure.authorization.hbase.XaSecureAuthorizationCoprocessor')

    # Recommend configs for bucket cache
    threshold = 23 # 2 Gb is reserved for other offheap memory
    mb = 1024
    if (int(clusterData["hbaseRam"]) > threshold):
      # To enable cache - calculate values
      regionserver_total_ram = int(clusterData["hbaseRam"]) * mb
      regionserver_heap_size = 20480
      regionserver_max_direct_memory_size = regionserver_total_ram - regionserver_heap_size
      hfile_block_cache_size = '0.4'
      block_cache_heap = 8192 # int(regionserver_heap_size * hfile_block_cache_size)
      hbase_regionserver_global_memstore_size = '0.4'
      reserved_offheap_memory = 2048
      bucketcache_offheap_memory = regionserver_max_direct_memory_size - reserved_offheap_memory
      hbase_bucketcache_size = block_cache_heap + bucketcache_offheap_memory
      hbase_bucketcache_percentage_in_combinedcache = float(bucketcache_offheap_memory) / hbase_bucketcache_size
      hbase_bucketcache_percentage_in_combinedcache_str = "{0:.4f}".format(math.ceil(hbase_bucketcache_percentage_in_combinedcache * 10000) / 10000.0)

      # Set values in hbase-site
      putHbaseSiteProperty('hfile.block.cache.size', hfile_block_cache_size)
      putHbaseSiteProperty('hbase.regionserver.global.memstore.size', hbase_regionserver_global_memstore_size)
      putHbaseSiteProperty('hbase.bucketcache.ioengine', 'offheap')
      putHbaseSiteProperty('hbase.bucketcache.size', hbase_bucketcache_size)
      putHbaseSiteProperty('hbase.bucketcache.percentage.in.combinedcache', hbase_bucketcache_percentage_in_combinedcache_str)

      # Enable in hbase-env
      putHbaseEnvProperty = self.putProperty(configurations, "hbase-env", services)
      putHbaseEnvProperty('hbase_max_direct_memory_size', regionserver_max_direct_memory_size)
      putHbaseEnvProperty('hbase_regionserver_heapsize', regionserver_heap_size)
    else:
      # Disable
      putHbaseSitePropertyAttributes('hbase.bucketcache.ioengine', 'delete', 'true')
      putHbaseSitePropertyAttributes('hbase.bucketcache.size', 'delete', 'true')
      putHbaseSitePropertyAttributes('hbase.bucketcache.percentage.in.combinedcache', 'delete', 'true')
      putHbaseEnvPropertyAttributes('hbase_max_direct_memory_size', 'delete', 'true')

    # Authorization
    hbase_coprocessor_region_classes = None
    if 'hbase.coprocessor.region.classes' in configurations["hbase-site"]["properties"]:
      hbase_coprocessor_region_classes = configurations["hbase-site"]["properties"]["hbase.coprocessor.region.classes"].strip()
    elif 'hbase-site' in services['configurations'] and 'hbase.coprocessor.region.classes' in services['configurations']["hbase-site"]["properties"]:
      hbase_coprocessor_region_classes = services['configurations']["hbase-site"]["properties"]["hbase.coprocessor.region.classes"].strip()
    if hbase_coprocessor_region_classes:
      coprocessorRegionClassList = hbase_coprocessor_region_classes.split(',')
    else:
      coprocessorRegionClassList = []
    # If configurations has it - it has priority as it is calculated. Then, the service's configurations will be used.
    hbase_security_authorization = None
    if 'hbase-site' in configurations and 'hbase.security.authorization' in configurations['hbase-site']['properties']:
      hbase_security_authorization = configurations['hbase-site']['properties']['hbase.security.authorization']
    elif 'hbase-site' in services['configurations'] and 'hbase.security.authorization' in services['configurations']['hbase-site']['properties']:
      hbase_security_authorization = services['configurations']['hbase-site']['properties']['hbase.security.authorization']
    if hbase_security_authorization:
      if 'true' == hbase_security_authorization.lower():
        putHbaseSiteProperty('hbase.coprocessor.master.classes', "org.apache.hadoop.hbase.security.access.AccessController")
        coprocessorRegionClassList.append("org.apache.hadoop.hbase.security.access.SecureBulkLoadEndpoint")
        coprocessorRegionClassList.append("org.apache.hadoop.hbase.security.access.AccessController")
        putHbaseSiteProperty('hbase.coprocessor.regionserver.classes', "org.apache.hadoop.hbase.security.access.AccessController")
      else:
        putHbaseSiteProperty('hbase.coprocessor.master.classes', "")
        coprocessorRegionClassList.append("org.apache.hadoop.hbase.security.access.SecureBulkLoadEndpoint")
        putHbaseSitePropertyAttributes('hbase.coprocessor.regionserver.classes', 'delete', 'true')
    else:
      coprocessorRegionClassList.append("org.apache.hadoop.hbase.security.access.SecureBulkLoadEndpoint")
      putHbaseSitePropertyAttributes('hbase.coprocessor.regionserver.classes', 'delete', 'true')

    # Authentication
    if 'hbase-site' in services['configurations'] and 'hbase.security.authentication' in services['configurations']['hbase-site']['properties']:
      if 'kerberos' == services['configurations']['hbase-site']['properties']['hbase.security.authentication'].lower():
        if 'org.apache.hadoop.hbase.security.access.SecureBulkLoadEndpoint' not in coprocessorRegionClassList:
          coprocessorRegionClassList.append('org.apache.hadoop.hbase.security.access.SecureBulkLoadEndpoint')
        if 'org.apache.hadoop.hbase.security.token.TokenProvider' not in coprocessorRegionClassList:
          coprocessorRegionClassList.append('org.apache.hadoop.hbase.security.token.TokenProvider')
      else:
        if 'org.apache.hadoop.hbase.security.token.TokenProvider' in coprocessorRegionClassList:
          coprocessorRegionClassList.remove('org.apache.hadoop.hbase.security.token.TokenProvider')

    #Remove duplicates
    uniqueCoprocessorRegionClassList = []
    [uniqueCoprocessorRegionClassList.append(i) for i in coprocessorRegionClassList if not uniqueCoprocessorRegionClassList.count(i)]
    putHbaseSiteProperty('hbase.coprocessor.region.classes', ','.join(set(uniqueCoprocessorRegionClassList)))


  def recommendTezConfigurations(self, configurations, clusterData, services, hosts):
    if not "yarn-site" in configurations:
      self.recommendYARNConfigurations(configurations, clusterData, services, hosts)
    #properties below should be always present as they are provided in HDP206 stack advisor
    yarnMaxAllocationSize = min(30 * int(configurations["yarn-site"]["properties"]["yarn.scheduler.minimum-allocation-mb"]), int(configurations["yarn-site"]["properties"]["yarn.scheduler.maximum-allocation-mb"]))

    putTezProperty = self.putProperty(configurations, "tez-site")
    putTezProperty("tez.am.resource.memory.mb", int(clusterData['amMemory']) * 2 if int(clusterData['amMemory']) < 3072 else int(clusterData['amMemory']))

    taskResourceMemory = clusterData['mapMemory'] if clusterData['mapMemory'] > 2048 else int(clusterData['reduceMemory'])
    taskResourceMemory = min(clusterData['containers'] * clusterData['ramPerContainer'], taskResourceMemory, yarnMaxAllocationSize)
    putTezProperty("tez.task.resource.memory.mb", taskResourceMemory)
    putTezProperty("tez.runtime.io.sort.mb", min(int(taskResourceMemory * 0.4), 2047))
    putTezProperty("tez.runtime.unordered.output.buffer.size-mb", int(taskResourceMemory * 0.075))
    putTezProperty("tez.session.am.dag.submit.timeout.secs", "600")

  def getServiceConfigurationValidators(self):
    parentValidators = super(HDP22StackAdvisor, self).getServiceConfigurationValidators()
    childValidators = {
      "HDFS": {"hdfs-site": self.validateHDFSConfigurations,
               "hadoop-env": self.validateHDFSConfigurationsEnv},
      "YARN": {"yarn-env": self.validateYARNEnvConfigurations},
      "HIVE": {"hiveserver2-site": self.validateHiveServer2Configurations,
               "hive-site": self.validateHiveConfigurations,
               "hive-env": self.validateHiveConfigurationsEnv},
      "HBASE": {"hbase-site": self.validateHBASEConfigurations,
                "hbase-env": self.validateHBASEEnvConfigurations},
      "MAPREDUCE2": {"mapred-site": self.validateMapReduce2Configurations},
      "TEZ": {"tez-site": self.validateTezConfigurations}
    }
    self.mergeValidators(parentValidators, childValidators)
    return parentValidators

  def validateTezConfigurations(self, properties, recommendedDefaults, configurations, services, hosts):
    validationItems = [ {"config-name": 'tez.am.resource.memory.mb', "item": self.validatorLessThenDefaultValue(properties, recommendedDefaults, 'tez.am.resource.memory.mb')},
                        {"config-name": 'tez.task.resource.memory.mb', "item": self.validatorLessThenDefaultValue(properties, recommendedDefaults, 'tez.task.resource.memory.mb')},
                        {"config-name": 'tez.runtime.io.sort.mb', "item": self.validatorLessThenDefaultValue(properties, recommendedDefaults, 'tez.runtime.io.sort.mb')},
                        {"config-name": 'tez.runtime.unordered.output.buffer.size-mb', "item": self.validatorLessThenDefaultValue(properties, recommendedDefaults, 'tez.runtime.unordered.output.buffer.size-mb')},]

    tez_site = properties
    prop_name1 = 'tez.am.resource.memory.mb'
    prop_name2 = 'tez.task.resource.memory.mb'
    yarnSiteProperties = getSiteProperties(configurations, "yarn-site")
    if yarnSiteProperties:
      yarnMaxAllocationSize = min(30 * int(configurations["yarn-site"]["properties"]["yarn.scheduler.minimum-allocation-mb"]),int(configurations["yarn-site"]["properties"]["yarn.scheduler.maximum-allocation-mb"]))
      if int(tez_site[prop_name1]) > yarnMaxAllocationSize:
          validationItems.append({"config-name": prop_name1,
                                  "item": self.getWarnItem(
                                      "{0} should be less than YARN max allocation size ({1})".format(prop_name1, yarnMaxAllocationSize))})
      if int(tez_site[prop_name2]) > yarnMaxAllocationSize:
          validationItems.append({"config-name": prop_name2,
                                  "item": self.getWarnItem(
                                      "{0} should be less than YARN max allocation size ({1})".format(prop_name2, yarnMaxAllocationSize))})

    return self.toConfigurationValidationProblems(validationItems, "tez-site")

  def recommendMapReduce2Configurations(self, configurations, clusterData, services, hosts):
    self.recommendYARNConfigurations(configurations, clusterData, services, hosts)
    putMapredProperty = self.putProperty(configurations, "mapred-site", services)
    nodemanagerMinRam = 1048576 # 1TB in mb
    for nodemanager in self.getHostsWithComponent("YARN", "NODEMANAGER", services, hosts):
      nodemanagerMinRam = min(nodemanager["Hosts"]["total_mem"]/1024, nodemanagerMinRam)
    putMapredProperty('yarn.app.mapreduce.am.resource.mb', configurations["yarn-site"]["properties"]["yarn.scheduler.minimum-allocation-mb"])
    putMapredProperty('yarn.app.mapreduce.am.command-opts', "-Xmx" + str(int(0.8 * int(configurations["mapred-site"]["properties"]["yarn.app.mapreduce.am.resource.mb"]))) + "m" + " -Dhdp.version=${hdp.version}")
    servicesList = [service["StackServices"]["service_name"] for service in services["services"]]
    min_mapreduce_map_memory_mb = 0
    min_mapreduce_reduce_memory_mb = 0
    min_mapreduce_map_java_opts = 0
    if ("PIG" in servicesList):
      min_mapreduce_map_memory_mb = 1536
      min_mapreduce_reduce_memory_mb = 1536
      min_mapreduce_map_java_opts = 1024
    putMapredProperty('mapreduce.map.memory.mb', max(min_mapreduce_map_memory_mb, int(configurations["yarn-site"]["properties"]["yarn.scheduler.minimum-allocation-mb"])))
    putMapredProperty('mapreduce.reduce.memory.mb', max(min_mapreduce_reduce_memory_mb, min(2*int(configurations["yarn-site"]["properties"]["yarn.scheduler.minimum-allocation-mb"]), int(nodemanagerMinRam))))
    mapredMapXmx = int(0.8*int(configurations["mapred-site"]["properties"]["mapreduce.map.memory.mb"]));
    putMapredProperty('mapreduce.map.java.opts', "-Xmx" + str(max(min_mapreduce_map_java_opts, mapredMapXmx)) + "m")
    putMapredProperty('mapreduce.reduce.java.opts', "-Xmx" + str(int(0.8*int(configurations["mapred-site"]["properties"]["mapreduce.reduce.memory.mb"]))) + "m")
    putMapredProperty('mapreduce.task.io.sort.mb', str(min(int(0.7*mapredMapXmx), 2047)))
    # Property Attributes
    putMapredPropertyAttribute = self.putPropertyAttribute(configurations, "mapred-site")
    yarnMinAllocationSize = int(configurations["yarn-site"]["properties"]["yarn.scheduler.minimum-allocation-mb"])
    yarnMaxAllocationSize = min(30 * int(configurations["yarn-site"]["properties"]["yarn.scheduler.minimum-allocation-mb"]), int(configurations["yarn-site"]["properties"]["yarn.scheduler.maximum-allocation-mb"]))
    putMapredPropertyAttribute("mapreduce.map.memory.mb", "maximum", yarnMaxAllocationSize)
    putMapredPropertyAttribute("mapreduce.map.memory.mb", "minimum", yarnMinAllocationSize)
    putMapredPropertyAttribute("mapreduce.reduce.memory.mb", "maximum", yarnMaxAllocationSize)
    putMapredPropertyAttribute("mapreduce.reduce.memory.mb", "minimum", yarnMinAllocationSize)
    putMapredPropertyAttribute("yarn.app.mapreduce.am.resource.mb", "maximum", yarnMaxAllocationSize)
    putMapredPropertyAttribute("yarn.app.mapreduce.am.resource.mb", "minimum", yarnMinAllocationSize)
    # Hadoop MR limitation
    putMapredPropertyAttribute("mapreduce.task.io.sort.mb", "maximum", "2047")

  def validateMapReduce2Configurations(self, properties, recommendedDefaults, configurations, services, hosts):
    validationItems = [ {"config-name": 'mapreduce.map.java.opts', "item": self.validateXmxValue(properties, recommendedDefaults, 'mapreduce.map.java.opts')},
                        {"config-name": 'mapreduce.reduce.java.opts', "item": self.validateXmxValue(properties, recommendedDefaults, 'mapreduce.reduce.java.opts')},
                        {"config-name": 'mapreduce.task.io.sort.mb', "item": self.validatorLessThenDefaultValue(properties, recommendedDefaults, 'mapreduce.task.io.sort.mb')},
                        {"config-name": 'mapreduce.map.memory.mb', "item": self.validatorLessThenDefaultValue(properties, recommendedDefaults, 'mapreduce.map.memory.mb')},
                        {"config-name": 'mapreduce.reduce.memory.mb', "item": self.validatorLessThenDefaultValue(properties, recommendedDefaults, 'mapreduce.reduce.memory.mb')},
                        {"config-name": 'yarn.app.mapreduce.am.resource.mb', "item": self.validatorLessThenDefaultValue(properties, recommendedDefaults, 'yarn.app.mapreduce.am.resource.mb')},
                        {"config-name": 'yarn.app.mapreduce.am.command-opts', "item": self.validateXmxValue(properties, recommendedDefaults, 'yarn.app.mapreduce.am.command-opts')}]

    if checkXmxValueFormat(properties['mapreduce.map.java.opts']):
      mapreduceMapJavaOpts = formatXmxSizeToBytes(getXmxSize(properties['mapreduce.map.java.opts'])) / (1024.0 * 1024)
      mapreduceMapMemoryMb = to_number(properties['mapreduce.map.memory.mb'])
      if mapreduceMapJavaOpts > mapreduceMapMemoryMb:
        validationItems.append({"config-name": 'mapreduce.map.java.opts', "item": self.getWarnItem("mapreduce.map.java.opts Xmx should be less than mapreduce.map.memory.mb ({0})".format(mapreduceMapMemoryMb))})

    if checkXmxValueFormat(properties['mapreduce.reduce.java.opts']):
      mapreduceReduceJavaOpts = formatXmxSizeToBytes(getXmxSize(properties['mapreduce.reduce.java.opts'])) / (1024.0 * 1024)
      mapreduceReduceMemoryMb = to_number(properties['mapreduce.reduce.memory.mb'])
      if mapreduceReduceJavaOpts > mapreduceReduceMemoryMb:
        validationItems.append({"config-name": 'mapreduce.reduce.java.opts', "item": self.getWarnItem("mapreduce.reduce.java.opts Xmx should be less than mapreduce.reduce.memory.mb ({0})".format(mapreduceReduceMemoryMb))})

    if checkXmxValueFormat(properties['yarn.app.mapreduce.am.command-opts']):
      yarnAppMapreduceAmCommandOpts = formatXmxSizeToBytes(getXmxSize(properties['yarn.app.mapreduce.am.command-opts'])) / (1024.0 * 1024)
      yarnAppMapreduceAmResourceMb = to_number(properties['yarn.app.mapreduce.am.resource.mb'])
      if yarnAppMapreduceAmCommandOpts > yarnAppMapreduceAmResourceMb:
        validationItems.append({"config-name": 'yarn.app.mapreduce.am.command-opts', "item": self.getWarnItem("yarn.app.mapreduce.am.command-opts Xmx should be less than yarn.app.mapreduce.am.resource.mb ({0})".format(yarnAppMapreduceAmResourceMb))})

    return self.toConfigurationValidationProblems(validationItems, "mapred-site")

  def validateHDFSConfigurationsEnv(self, properties, recommendedDefaults, configurations, services, hosts):
    validationItems = [ {"config-name": 'namenode_heapsize', "item": self.validatorLessThenDefaultValue(properties, recommendedDefaults, 'namenode_heapsize')},
                        {"config-name": 'namenode_opt_newsize', "item": self.validatorLessThenDefaultValue(properties, recommendedDefaults, 'namenode_opt_newsize')},
                        {"config-name": 'namenode_opt_maxnewsize', "item": self.validatorLessThenDefaultValue(properties, recommendedDefaults, 'namenode_opt_maxnewsize')}]
    return self.toConfigurationValidationProblems(validationItems, "hadoop-env")
  
  def validateHDFSConfigurations(self, properties, recommendedDefaults, configurations, services, hosts):
    # We can not access property hadoop.security.authentication from the
    # other config (core-site). That's why we are using another heuristics here
    hdfs_site = properties
    core_site = getSiteProperties(configurations, "core-site")

    dfs_encrypt_data_transfer = 'dfs.encrypt.data.transfer'  # Hadoop Wire encryption
    try:
      wire_encryption_enabled = hdfs_site[dfs_encrypt_data_transfer] == "true"
    except KeyError:
      wire_encryption_enabled = False

    HTTP_ONLY = 'HTTP_ONLY'
    HTTPS_ONLY = 'HTTPS_ONLY'
    HTTP_AND_HTTPS = 'HTTP_AND_HTTPS'

    VALID_HTTP_POLICY_VALUES = [HTTP_ONLY, HTTPS_ONLY, HTTP_AND_HTTPS]
    VALID_TRANSFER_PROTECTION_VALUES = ['authentication', 'integrity', 'privacy']

    validationItems = []
    address_properties = [
      # "dfs.datanode.address",
      # "dfs.datanode.http.address",
      # "dfs.datanode.https.address",
      # "dfs.datanode.ipc.address",
      # "dfs.journalnode.http-address",
      # "dfs.journalnode.https-address",
      # "dfs.namenode.rpc-address",
      # "dfs.namenode.secondary.http-address",
      "dfs.namenode.http-address",
      "dfs.namenode.https-address",
    ]
    #Validating *address properties for correct values

    for address_property in address_properties:
      if address_property in hdfs_site:
        value = hdfs_site[address_property]
        if not is_valid_host_port_authority(value):
          validationItems.append({"config-name" : address_property, "item" :
            self.getErrorItem(address_property + " does not contain a valid host:port authority: " + value)})

    #Adding Ranger Plugin logic here 
    ranger_plugin_properties = getSiteProperties(configurations, "ranger-hdfs-plugin-properties")
    ranger_plugin_enabled = ranger_plugin_properties['ranger-hdfs-plugin-enabled'] if ranger_plugin_properties else 'No'
    servicesList = [service["StackServices"]["service_name"] for service in services["services"]]
    if ("RANGER" in servicesList) and (ranger_plugin_enabled.lower() == 'Yes'.lower()):
      if hdfs_site['dfs.permissions.enabled'] != 'true':
        validationItems.append({"config-name": 'dfs.permissions.enabled',
                                    "item": self.getWarnItem(
                                      "dfs.permissions.enabled needs to be set to true if Ranger HDFS Plugin is enabled.")})

    if (not wire_encryption_enabled and   # If wire encryption is enabled at Hadoop, it disables all our checks
          core_site['hadoop.security.authentication'] == 'kerberos' and
          core_site['hadoop.security.authorization'] == 'true'):
      # security is enabled

      dfs_http_policy = 'dfs.http.policy'
      dfs_datanode_address = 'dfs.datanode.address'
      datanode_http_address = 'dfs.datanode.http.address'
      datanode_https_address = 'dfs.datanode.https.address'
      data_transfer_protection = 'dfs.data.transfer.protection'

      try: # Params may be absent
        privileged_dfs_dn_port = isSecurePort(getPort(hdfs_site[dfs_datanode_address]))
      except KeyError:
        privileged_dfs_dn_port = False
      try:
        privileged_dfs_http_port = isSecurePort(getPort(hdfs_site[datanode_http_address]))
      except KeyError:
        privileged_dfs_http_port = False
      try:
        privileged_dfs_https_port = isSecurePort(getPort(hdfs_site[datanode_https_address]))
      except KeyError:
        privileged_dfs_https_port = False
      try:
        dfs_http_policy_value = hdfs_site[dfs_http_policy]
      except KeyError:
        dfs_http_policy_value = HTTP_ONLY  # Default
      try:
        data_transfer_protection_value = hdfs_site[data_transfer_protection]
      except KeyError:
        data_transfer_protection_value = None

      if dfs_http_policy_value not in VALID_HTTP_POLICY_VALUES:
        validationItems.append({"config-name": dfs_http_policy,
                                "item": self.getWarnItem(
                                  "Invalid property value: {0}. Valid values are {1}".format(
                                    dfs_http_policy_value, VALID_HTTP_POLICY_VALUES))})

      # determine whether we use secure ports
      address_properties_with_warnings = []
      if dfs_http_policy_value == HTTPS_ONLY:
        if not privileged_dfs_dn_port and (privileged_dfs_https_port or datanode_https_address not in hdfs_site):
          important_properties = [dfs_datanode_address, datanode_https_address]
          message = "You set up datanode to use some non-secure ports. " \
                    "If you want to run Datanode under non-root user in a secure cluster, " \
                    "you should set all these properties {2} " \
                    "to use non-secure ports (if property {3} does not exist, " \
                    "just add it). You may also set up property {4} ('{5}' is a good default value). " \
                    "Also, set up WebHDFS with SSL as " \
                    "described in manual in order to be able to " \
                    "use HTTPS.".format(dfs_http_policy, dfs_http_policy_value, important_properties,
                                        datanode_https_address, data_transfer_protection,
                                        VALID_TRANSFER_PROTECTION_VALUES[0])
          address_properties_with_warnings.extend(important_properties)
      else:  # dfs_http_policy_value == HTTP_AND_HTTPS or HTTP_ONLY
        # We don't enforce datanode_https_address to use privileged ports here
        any_nonprivileged_ports_are_in_use = not privileged_dfs_dn_port or not privileged_dfs_http_port
        if any_nonprivileged_ports_are_in_use:
          important_properties = [dfs_datanode_address, datanode_http_address]
          message = "You have set up datanode to use some non-secure ports, but {0} is set to {1}. " \
                    "In a secure cluster, Datanode forbids using non-secure ports " \
                    "if {0} is not set to {3}. " \
                    "Please make sure that properties {2} use secure ports.".format(
                      dfs_http_policy, dfs_http_policy_value, important_properties, HTTPS_ONLY)
          address_properties_with_warnings.extend(important_properties)

      # Generate port-related warnings if any
      for prop in address_properties_with_warnings:
        validationItems.append({"config-name": prop,
                                "item": self.getWarnItem(message)})

      # Check if it is appropriate to use dfs.data.transfer.protection
      if data_transfer_protection_value is not None:
        if dfs_http_policy_value in [HTTP_ONLY, HTTP_AND_HTTPS]:
          validationItems.append({"config-name": data_transfer_protection,
                                  "item": self.getWarnItem(
                                    "{0} property can not be used when {1} is set to any "
                                    "value other then {2}. Tip: When {1} property is not defined, it defaults to {3}".format(
                                    data_transfer_protection, dfs_http_policy, HTTPS_ONLY, HTTP_ONLY))})
        elif not data_transfer_protection_value in VALID_TRANSFER_PROTECTION_VALUES:
          validationItems.append({"config-name": data_transfer_protection,
                                  "item": self.getWarnItem(
                                    "Invalid property value: {0}. Valid values are {1}.".format(
                                      data_transfer_protection_value, VALID_TRANSFER_PROTECTION_VALUES))})
    return self.toConfigurationValidationProblems(validationItems, "hdfs-site")

  def validateHiveServer2Configurations(self, properties, recommendedDefaults, configurations, services, hosts):
    hive_server2 = properties
    validationItems = [] 
    #Adding Ranger Plugin logic here 
    ranger_plugin_properties = getSiteProperties(configurations, "ranger-hive-plugin-properties")
    hive_env_properties = getSiteProperties(configurations, "hive-env")
    ranger_plugin_enabled = 'hive_security_authorization' in hive_env_properties and hive_env_properties['hive_security_authorization'].lower() == 'ranger'
    servicesList = [service["StackServices"]["service_name"] for service in services["services"]]
    ##Add stack validations only if Ranger is enabled.
    if ("RANGER" in servicesList):
      ##Add stack validations for  Ranger plugin enabled.
      if ranger_plugin_enabled:
        prop_name = 'hive.security.authorization.manager'
        prop_val = "com.xasecure.authorization.hive.authorizer.XaSecureHiveAuthorizerFactory"
        if hive_server2[prop_name] != prop_val:
          validationItems.append({"config-name": prop_name,
                                  "item": self.getWarnItem(
                                  "If Ranger Hive Plugin is enabled."\
                                  " {0} needs to be set to {1}".format(prop_name,prop_val))})
        prop_name = 'hive.security.authenticator.manager'
        prop_val = "org.apache.hadoop.hive.ql.security.SessionStateUserAuthenticator"
        if hive_server2[prop_name] != prop_val:
          validationItems.append({"config-name": prop_name,
                                  "item": self.getWarnItem(
                                  "If Ranger Hive Plugin is enabled."\
                                  " {0} needs to be set to {1}".format(prop_name,prop_val))})
      ##Add stack validations for  Ranger plugin disabled.
      elif not ranger_plugin_enabled:
        prop_name = 'hive.security.authorization.manager'
        prop_val = "org.apache.hadoop.hive.ql.security.authorization.plugin.sqlstd.SQLStdHiveAuthorizerFactory"
        if hive_server2[prop_name] != prop_val:
          validationItems.append({"config-name": prop_name,
                                  "item": self.getWarnItem(
                                  "If Ranger Hive Plugin is disabled."\
                                  " {0} needs to be set to {1}".format(prop_name,prop_val))})
        prop_name = 'hive.security.authenticator.manager'
        prop_val = "org.apache.hadoop.hive.ql.security.SessionStateUserAuthenticator"
        if hive_server2[prop_name] != prop_val:
          validationItems.append({"config-name": prop_name,
                                  "item": self.getWarnItem(
                                  "If Ranger Hive Plugin is disabled."\
                                  " {0} needs to be set to {1}".format(prop_name,prop_val))})
    return self.toConfigurationValidationProblems(validationItems, "hiveserver2-site")

  def validateHiveConfigurationsEnv(self, properties, recommendedDefaults, configurations, services, hosts):
    validationItems = []
    hive_env = properties
    hive_site = getSiteProperties(configurations, "hive-site")
    if str(hive_env["hive_security_authorization"]).lower() == "none" \
      and str(hive_site["hive.security.authorization.enabled"]).lower() == "true":
      authorization_item = self.getErrorItem("hive_security_authorization should not be None "
                                             "if hive.security.authorization.enabled is set")
      validationItems.append({"config-name": "hive_security_authorization", "item": authorization_item})

    return self.toConfigurationValidationProblems(validationItems, "hive-env")

  def validateHiveConfigurations(self, properties, recommendedDefaults, configurations, services, hosts):
    parentValidationProblems = super(HDP22StackAdvisor, self).validateHiveConfigurations(properties, recommendedDefaults, configurations, services, hosts)
    hive_site = properties
    validationItems = []
    #Adding Ranger Plugin logic here
    ranger_plugin_properties = getSiteProperties(configurations, "ranger-hive-plugin-properties")
    hive_env_properties = getSiteProperties(configurations, "hive-env")
    ranger_plugin_enabled = 'hive_security_authorization' in hive_env_properties and hive_env_properties['hive_security_authorization'].lower() == 'ranger'
    servicesList = [service["StackServices"]["service_name"] for service in services["services"]]
    ##Add stack validations only if Ranger is enabled.
    if ("RANGER" in servicesList):
      ##Add stack validations for  Ranger plugin enabled.
      if ranger_plugin_enabled:
        prop_name = 'hive.security.authorization.enabled'
        prop_val = 'true'
        if hive_site[prop_name] != prop_val:
          validationItems.append({"config-name": prop_name,
                                  "item": self.getWarnItem(
                                    "If Ranger Hive Plugin is enabled." \
                                    " {0} needs to be set to {1}".format(prop_name,prop_val))})

        prop_name = 'hive.conf.restricted.list'
        prop_vals = 'hive.security.authorization.enabled,hive.security.authorization.manager,hive.security.authenticator.manager'.split(',')
        current_vals = hive_site[prop_name].split(',')
        missing_vals = []

        for val in prop_vals:
          if not val in current_vals:
            missing_vals.append(val)

        if missing_vals:
          validationItems.append({"config-name": prop_name,
                                  "item": self.getWarnItem(
                                  "If Ranger Hive Plugin is enabled." \
                                  " {0} needs to contain {1}".format(prop_name, ','.join(missing_vals)))})
    stripe_size_values = [8388608, 16777216, 33554432, 67108864, 134217728, 268435456]
    stripe_size_property = "hive.exec.orc.default.stripe.size"
    if int(properties[stripe_size_property]) not in stripe_size_values:
      validationItems.append({"config-name": stripe_size_property,
                              "item": self.getWarnItem("Correct values are {0}".format(stripe_size_values))
                             }
      )
    configurationValidationProblems = self.toConfigurationValidationProblems(validationItems, "hive-site")
    configurationValidationProblems.extend(parentValidationProblems)
    return configurationValidationProblems

  def validateHBASEConfigurations(self, properties, recommendedDefaults, configurations, services, hosts):
    hbase_site = properties
    validationItems = []

    prop_name1 = 'hbase.regionserver.global.memstore.size'
    prop_name2 = 'hfile.block.cache.size'
    props_max_sum = 0.8

    if not is_number(hbase_site[prop_name1]):
      validationItems.append({"config-name": prop_name1,
                              "item": self.getWarnItem(
                              "{0} should be float value".format(prop_name1))})
    elif not is_number(hbase_site[prop_name2]):
      validationItems.append({"config-name": prop_name2,
                              "item": self.getWarnItem(
                              "{0} should be float value".format(prop_name2))})
    elif float(hbase_site[prop_name1]) + float(hbase_site[prop_name2]) > props_max_sum:
      validationItems.append({"config-name": prop_name1,
                              "item": self.getWarnItem(
                              "{0} and {1} sum should not exceed {2}".format(prop_name1, prop_name2, props_max_sum))})

    #Adding Ranger Plugin logic here 
    ranger_plugin_properties = getSiteProperties(configurations, "ranger-hbase-plugin-properties")
    ranger_plugin_enabled = ranger_plugin_properties['ranger-hbase-plugin-enabled'] if ranger_plugin_properties else 'No'
    prop_name = 'hbase.security.authorization'
    prop_val = "true"
    servicesList = [service["StackServices"]["service_name"] for service in services["services"]]
    if ("RANGER" in servicesList) and (ranger_plugin_enabled.lower() == 'Yes'.lower()):
      if hbase_site[prop_name] != prop_val:
        validationItems.append({"config-name": prop_name,
                                "item": self.getWarnItem(
                                "If Ranger HBase Plugin is enabled."\
                                "{0} needs to be set to {1}".format(prop_name,prop_val))})
      prop_name = "hbase.coprocessor.master.classes"
      prop_val = "com.xasecure.authorization.hbase.XaSecureAuthorizationCoprocessor"
      exclude_val = "org.apache.hadoop.hbase.security.access.AccessController"
      if (prop_val in hbase_site[prop_name] and exclude_val not in hbase_site[prop_name]):
        pass
      else:
        validationItems.append({"config-name": prop_name,
                                "item": self.getWarnItem(
                                "If Ranger HBase Plugin is enabled."\
                                " {0} needs to contain {1} instead of {2}".format(prop_name,prop_val,exclude_val))})
      prop_name = "hbase.coprocessor.region.classes"
      prop_val = "com.xasecure.authorization.hbase.XaSecureAuthorizationCoprocessor"
      if (prop_val in hbase_site[prop_name] and exclude_val not in hbase_site[prop_name]):
        pass
      else:
        validationItems.append({"config-name": prop_name,
                                "item": self.getWarnItem(
                                "If Ranger HBase Plugin is enabled."\
                                " {0} needs to contain {1} instead of {2}".format(prop_name,prop_val,exclude_val))})

    # Validate bucket cache correct config
    prop_name = "hbase.bucketcache.ioengine"
    prop_val = "offheap"
    if prop_name in hbase_site and not (not hbase_site[prop_name] or hbase_site[prop_name] == prop_val):
      validationItems.append({"config-name": prop_name,
                              "item": self.getWarnItem(
                                "Recommended values of " \
                                " {0} is empty or '{1}'".format(prop_name,prop_val))})

    prop_name1 = "hbase.bucketcache.ioengine"
    prop_name2 = "hbase.bucketcache.size"
    prop_name3 = "hbase.bucketcache.percentage.in.combinedcache"

    if prop_name1 in hbase_site and prop_name2 in hbase_site and hbase_site[prop_name1] and not hbase_site[prop_name2]:
      validationItems.append({"config-name": prop_name2,
                              "item": self.getWarnItem(
                                "If bucketcache ioengine is enabled, {0} should be set".format(prop_name2))})
    if prop_name1 in hbase_site and prop_name3 in hbase_site and hbase_site[prop_name1] and not hbase_site[prop_name3]:
      validationItems.append({"config-name": prop_name3,
                              "item": self.getWarnItem(
                                "If bucketcache ioengine is enabled, {0} should be set".format(prop_name3))})

    # Validate hbase.security.authentication. 
    # Kerberos works only when security enabled.
    if "hbase.security.authentication" in properties:
      hbase_security_kerberos = properties["hbase.security.authentication"].lower() == "kerberos"
      core_site_properties = getSiteProperties(configurations, "core-site")
      security_enabled = False
      if core_site_properties:
        security_enabled = core_site_properties['hadoop.security.authentication'] == 'kerberos' and core_site_properties['hadoop.security.authorization'] == 'true'
      if not security_enabled and hbase_security_kerberos:
        validationItems.append({"config-name": "hbase.security.authentication",
                              "item": self.getWarnItem("Cluster must be secured with Kerberos before hbase.security.authentication's value of kerberos will have effect")})

    return self.toConfigurationValidationProblems(validationItems, "hbase-site")

  def validateHBASEEnvConfigurations(self, properties, recommendedDefaults, configurations, services, hosts):
    hbase_env = properties
    validationItems = [ {"config-name": 'hbase_regionserver_heapsize', "item": self.validatorLessThenDefaultValue(properties, recommendedDefaults, 'hbase_regionserver_heapsize')},
                        {"config-name": 'hbase_master_heapsize', "item": self.validatorLessThenDefaultValue(properties, recommendedDefaults, 'hbase_master_heapsize')} ]
    prop_name = "hbase_max_direct_memory_size"
    hbase_site_properties = getSiteProperties(configurations, "hbase-site")
    prop_name1 = "hbase.bucketcache.ioengine"

    if prop_name1 in hbase_site_properties and prop_name in hbase_env and hbase_site_properties[prop_name1] and hbase_site_properties[prop_name1] == "offheap" and not hbase_env[prop_name]:
      validationItems.append({"config-name": prop_name,
                              "item": self.getWarnItem(
                                "If bucketcache ioengine is enabled, {0} should be set".format(prop_name))})

    return self.toConfigurationValidationProblems(validationItems, "hbase-env")

  def validateYARNEnvConfigurations(self, properties, recommendedDefaults, configurations, services, hosts):
    validationItems = []
    if "yarn_cgroups_enabled" in properties:
      yarn_cgroups_enabled = properties["yarn_cgroups_enabled"].lower() == "true"
      core_site_properties = getSiteProperties(configurations, "core-site")
      security_enabled = False
      if core_site_properties:
        security_enabled = core_site_properties['hadoop.security.authentication'] == 'kerberos' and core_site_properties['hadoop.security.authorization'] == 'true'
      if not security_enabled and yarn_cgroups_enabled:
        validationItems.append({"config-name": "yarn_cgroups_enabled",
                              "item": self.getWarnItem("CPU Isolation should only be enabled if security is enabled")})
    return self.toConfigurationValidationProblems(validationItems, "yarn-env")

  def getMastersWithMultipleInstances(self):
    result = super(HDP22StackAdvisor, self).getMastersWithMultipleInstances()
    result.extend(['METRICS_COLLECTOR'])
    return result

  def getNotValuableComponents(self):
    result = super(HDP22StackAdvisor, self).getNotValuableComponents()
    result.extend(['METRICS_MONITOR'])
    return result

  def getNotPreferableOnServerComponents(self):
    result = super(HDP22StackAdvisor, self).getNotPreferableOnServerComponents()
    result.extend(['METRICS_COLLECTOR'])
    return result

  def getCardinalitiesDict(self):
    result = super(HDP22StackAdvisor, self).getCardinalitiesDict()
    result['METRICS_COLLECTOR'] = {"min": 1}
    return result

  def getAffectedConfigs(self, services):
    affectedConfigs = super(HDP22StackAdvisor, self).getAffectedConfigs(services)

    # There are configs that are not defined in the stack but added/removed by 
    # stack-advisor. Here we add such configs in order to clear the config
    # filtering down in base class
    configsList = [affectedConfig["type"] + "/" + affectedConfig["name"] for affectedConfig in affectedConfigs]
    if 'yarn-env/yarn_cgroups_enabled' in configsList:
      if 'yarn-site/yarn.nodemanager.container-executor.class' not in configsList:
        affectedConfigs.append({"type": "yarn-site", "name": "yarn.nodemanager.container-executor.class"})
      if 'yarn-site/yarn.nodemanager.container-executor.group' not in configsList:
        affectedConfigs.append({"type": "yarn-site", "name": "yarn.nodemanager.container-executor.group"})
      if 'yarn-site/yarn.nodemanager.container-executor.resources-handler.class' not in configsList:
        affectedConfigs.append({"type": "yarn-site", "name": "yarn.nodemanager.container-executor.resources-handler.class"})
      if 'yarn-site/yarn.nodemanager.container-executor.cgroups.hierarchy' not in configsList:
        affectedConfigs.append({"type": "yarn-site", "name": "yarn.nodemanager.container-executor.cgroups.hierarchy"})
      if 'yarn-site/yarn.nodemanager.container-executor.cgroups.mount' not in configsList:
        affectedConfigs.append({"type": "yarn-site", "name": "yarn.nodemanager.container-executor.cgroups.mount"})
      if 'yarn-site/yarn.nodemanager.linux-container-executor.cgroups.mount-path' not in configsList:
        affectedConfigs.append({"type": "yarn-site", "name": "yarn.nodemanager.linux-container-executor.cgroups.mount-path"})

    return affectedConfigs;

def is_number(s):
  try:
    float(s)
    return True
  except ValueError:
    pass

  return False

def is_valid_host_port_authority(target):
  has_scheme = "://" in target
  if not has_scheme:
    target = "dummyscheme://"+target
  try:
    result = urlparse(target)
    if result.hostname is not None and result.port is not None:
      return True
  except ValueError:
    pass
  return False
