# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Set Hadoop-specific environment variables here - Task 2.2 requirement

# Java Home - Critical for Hadoop operation
export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64

# Hadoop installation directory
export HADOOP_HOME=/opt/hadoop
export HADOOP_CONF_DIR=${HADOOP_HOME}/etc/hadoop
export HADOOP_COMMON_HOME=${HADOOP_HOME}
export HADOOP_HDFS_HOME=${HADOOP_HOME}
export HADOOP_MAPRED_HOME=${HADOOP_HOME}
export HADOOP_YARN_HOME=${HADOOP_HOME}

# Hadoop classpath
export HADOOP_CLASSPATH=${JAVA_HOME}/lib/tools.jar

# Memory settings for Hadoop daemons
export HADOOP_HEAPSIZE=2048
export HADOOP_NAMENODE_INIT_HEAPSIZE=2048

# Log directory
export HADOOP_LOG_DIR=${HADOOP_HOME}/logs

# PID directory
export HADOOP_PID_DIR=${HADOOP_HOME}/pids

# Security options
export HADOOP_SECURE_DN_USER=
export HADOOP_SECURE_DN_LOG_DIR=
export HADOOP_SECURE_DN_PID_DIR=

# Optional: Set JVM options for Hadoop processes
export HADOOP_OPTS="-Djava.net.preferIPv4Stack=true"
export HADOOP_NAMENODE_OPTS="-server -XX:ParallelGCThreads=8 -XX:+UseConcMarkSweepGC -XX:ErrorFile=${HADOOP_LOG_DIR}/hs_err_pid%p.log -XX:NewSize=200m -XX:MaxNewSize=200m -Xloggc:${HADOOP_LOG_DIR}/gc.log-$(date +'%Y%m%d%H%M') -verbose:gc -XX:+PrintGCDetails -XX:+PrintGCTimeStamps -XX:+PrintGCDateStamps -Xms2048m -Xmx2048m -Dhadoop.security.logger=INFO,RFAS -Dhdfs.audit.logger=INFO,NullAppender ${HADOOP_NAMENODE_OPTS}"
export HADOOP_DATANODE_OPTS="-server -XX:ParallelGCThreads=4 -XX:+UseConcMarkSweepGC -XX:ErrorFile=${HADOOP_LOG_DIR}/hs_err_pid%p.log -XX:NewSize=200m -XX:MaxNewSize=200m -Xloggc:${HADOOP_LOG_DIR}/gc.log-$(date +'%Y%m%d%H%M') -verbose:gc -XX:+PrintGCDetails -XX:+PrintGCTimeStamps -XX:+PrintGCDateStamps -Xms1024m -Xmx1024m -Dhadoop.security.logger=ERROR,RFAS ${HADOOP_DATANODE_OPTS}"

# For development purposes - disable security warnings
export HADOOP_OPTS="${HADOOP_OPTS} -Djava.security.egd=file:/dev/./urandom"