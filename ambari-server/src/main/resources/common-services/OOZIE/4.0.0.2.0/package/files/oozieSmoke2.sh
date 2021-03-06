#!/usr/bin/env bash
#
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
#

export os_family=$1
export oozie_lib_dir=$2
export oozie_conf_dir=$3
export oozie_bin_dir=$4
export oozie_examples_dir=$5
export hadoop_conf_dir=$6
export hadoop_bin_dir=$7
export smoke_test_user=$8
export security_enabled=$9
export smoke_user_keytab=${10}
export kinit_path_local=${11}
export smokeuser_principal=${12}

function getValueFromField {
  xmllint $1 | grep "<name>$2</name>" -C 2 | grep '<value>' | cut -d ">" -f2 | cut -d "<" -f1
  return $?
}

function checkOozieJobStatus {
  local job_id=$1
  local num_of_tries=$2
  #default num_of_tries to 10 if not present
  num_of_tries=${num_of_tries:-10}
  local i=0
  local rc=1
  local cmd="source ${oozie_conf_dir}/oozie-env.sh ; ${oozie_bin_dir}/oozie job -oozie ${OOZIE_SERVER} -info $job_id"
  /var/lib/ambari-agent/ambari-sudo.sh su ${smoke_test_user} -s /bin/bash - -c "$cmd"
  while [ $i -lt $num_of_tries ] ; do
    cmd_output=`/var/lib/ambari-agent/ambari-sudo.sh su ${smoke_test_user} -s /bin/bash - -c "$cmd"`
    (IFS='';echo $cmd_output)
    act_status=$(IFS='';echo $cmd_output | grep ^Status | cut -d':' -f2 | sed 's| ||g')
    echo "workflow_status=$act_status"
    if [ "RUNNING" == "$act_status" ]; then
      #increment the counter and get the status again after waiting for 15 secs
      sleep 15
      (( i++ ))
      elif [ "SUCCEEDED" == "$act_status" ]; then
        rc=0;
        break;
      else
        rc=1
        break;
      fi
    done
    return $rc
}

export OOZIE_EXIT_CODE=0
export OOZIE_SERVER=`getValueFromField ${oozie_conf_dir}/oozie-site.xml oozie.base.url | tr '[:upper:]' '[:lower:]'`

cd $oozie_examples_dir

if [[ $security_enabled == "True" ]]; then
  kinitcmd="${kinit_path_local} -kt ${smoke_user_keytab} ${smokeuser_principal}; "
else 
  kinitcmd=""
fi

cmd="${kinitcmd}source ${oozie_conf_dir}/oozie-env.sh ; ${oozie_bin_dir}/oozie -Doozie.auth.token.cache=false job -oozie $OOZIE_SERVER -config $oozie_examples_dir/examples/apps/map-reduce/job.properties  -run"
echo $cmd
job_info=`/var/lib/ambari-agent/ambari-sudo.sh su ${smoke_test_user} -s /bin/bash - -c "$cmd" | grep "job:"`
job_id="`echo $job_info | cut -d':' -f2`"
checkOozieJobStatus "$job_id" 15
OOZIE_EXIT_CODE="$?"
exit $OOZIE_EXIT_CODE
