/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.apache.ambari.server.checks;

import java.util.HashMap;
import java.util.Map;
import java.util.Properties;

import org.apache.ambari.server.configuration.Configuration;
import org.apache.ambari.server.controller.PrereqCheckRequest;
import org.apache.ambari.server.orm.entities.ClusterVersionEntity;
import org.apache.ambari.server.orm.entities.RepositoryVersionEntity;
import org.apache.ambari.server.state.Cluster;
import org.apache.ambari.server.state.Clusters;
import org.apache.ambari.server.state.Config;
import org.apache.ambari.server.state.DesiredConfig;
import org.apache.ambari.server.state.Service;
import org.apache.ambari.server.state.StackId;
import org.apache.ambari.server.state.stack.PrereqCheckStatus;
import org.apache.ambari.server.state.stack.PrerequisiteCheck;
import org.junit.Assert;
import org.junit.Before;
import org.junit.Test;
import org.mockito.Mockito;

import com.google.inject.Provider;

/**
 * Tests for {@link YarnTimelineServerStatePreservingCheckTest}
 */
public class YarnTimelineServerStatePreservingCheckTest {
  private final Clusters m_clusters = Mockito.mock(Clusters.class);

  private final YarnTimelineServerStatePreservingCheck m_check = new YarnTimelineServerStatePreservingCheck();

  /**
   *
   */
  @Before
  public void setup() {
    m_check.clustersProvider = new Provider<Clusters>() {

      @Override
      public Clusters get() {
        return m_clusters;
      }
    };
  }

  /**
   * @throws Exception
   */
  @Test
  public void testIsApplicable() throws Exception {
    //Default value
    Configuration conf = new Configuration(new Properties());
    m_check._configuration = conf;

    final Cluster cluster = Mockito.mock(Cluster.class);
    Mockito.when(cluster.getClusterId()).thenReturn(1L);
    Mockito.when(m_clusters.getCluster("cluster")).thenReturn(cluster);
    Mockito.when(cluster.getCurrentStackVersion()).thenReturn(new StackId("HDP-2.2"));

    Map<String, Service> services = new HashMap<String, Service>();
    Mockito.when(cluster.getServices()).thenReturn(services);

    ClusterVersionEntity clusterVersionEntity = Mockito.mock(ClusterVersionEntity.class);
    Mockito.when(cluster.getCurrentClusterVersion()).thenReturn(clusterVersionEntity);

    RepositoryVersionEntity repositoryVersionEntity = Mockito.mock(RepositoryVersionEntity.class);
    Mockito.when(clusterVersionEntity.getRepositoryVersion()).thenReturn(repositoryVersionEntity);
    Mockito.when(repositoryVersionEntity.getVersion()).thenReturn("2.2.4.2");

    PrereqCheckRequest request = new PrereqCheckRequest("cluster");
    request.setRepositoryVersion("2.3.0.0");

    // YARN not installed
    Assert.assertFalse(m_check.isApplicable(request));

    // YARN installed
    services.put("YARN", Mockito.mock(Service.class));
    Assert.assertTrue(m_check.isApplicable(request));

    Mockito.when(repositoryVersionEntity.getVersion()).thenReturn("2.2.0.0");
    Assert.assertFalse(m_check.isApplicable(request));

    Mockito.when(repositoryVersionEntity.getVersion()).thenReturn("2.2.4.2");
    Assert.assertTrue(m_check.isApplicable(request));
    
    //Custom stack name and version
    Properties ambariProperties = new Properties();
    ambariProperties.setProperty("rollingupgrade.stack", "MYSTACK");
    ambariProperties.setProperty("rollingupgrade.version", "2.0.0.0");
    conf = new Configuration(ambariProperties);
    m_check._configuration = conf;
    
    Mockito.when(cluster.getClusterId()).thenReturn(1L);
    Mockito.when(m_clusters.getCluster("cluster")).thenReturn(cluster);
    Mockito.when(cluster.getCurrentStackVersion()).thenReturn(new StackId("MYSTACK-2.0"));

    services = new HashMap<String, Service>();
    Mockito.when(cluster.getServices()).thenReturn(services);

    clusterVersionEntity = Mockito.mock(ClusterVersionEntity.class);
    Mockito.when(cluster.getCurrentClusterVersion()).thenReturn(clusterVersionEntity);

    repositoryVersionEntity = Mockito.mock(RepositoryVersionEntity.class);
    Mockito.when(clusterVersionEntity.getRepositoryVersion()).thenReturn(repositoryVersionEntity);
    
    services.put("YARN", Mockito.mock(Service.class));

    Mockito.when(repositoryVersionEntity.getVersion()).thenReturn("1.0.0.0");
    Assert.assertFalse(m_check.isApplicable(request));

    Mockito.when(repositoryVersionEntity.getVersion()).thenReturn("4.1.0.0");
    Assert.assertTrue(m_check.isApplicable(request));
  }

  @Test
  public void testPerform() throws Exception {
    final Cluster cluster = Mockito.mock(Cluster.class);
    Mockito.when(cluster.getClusterId()).thenReturn(1L);
    Mockito.when(m_clusters.getCluster("cluster")).thenReturn(cluster);

    final DesiredConfig desiredConfig = Mockito.mock(DesiredConfig.class);
    Mockito.when(desiredConfig.getTag()).thenReturn("tag");
    Map<String, DesiredConfig> configMap = new HashMap<String, DesiredConfig>();
    configMap.put("yarn-site", desiredConfig);
    configMap.put("core-site", desiredConfig);

    Mockito.when(cluster.getDesiredConfigs()).thenReturn(configMap);
    final Config config = Mockito.mock(Config.class);
    Mockito.when(cluster.getConfig(Mockito.anyString(), Mockito.anyString())).thenReturn(config);
    final Map<String, String> properties = new HashMap<String, String>();
    Mockito.when(config.getProperties()).thenReturn(properties);

    PrerequisiteCheck check = new PrerequisiteCheck(null, null);
    m_check.perform(check, new PrereqCheckRequest("cluster"));
    Assert.assertEquals(PrereqCheckStatus.FAIL, check.getStatus());

    properties.put("yarn.timeline-service.recovery.enabled", "true");
    check = new PrerequisiteCheck(null, null);
    m_check.perform(check, new PrereqCheckRequest("cluster"));
    Assert.assertEquals(PrereqCheckStatus.PASS, check.getStatus());
  }
}
