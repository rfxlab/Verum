#!/usr/bin/env python
"""
 AUTHOR: Gabriel Bassett
 DATE: 12-17-2013
 DEPENDENCIES: a list of modules requiring installation
 Copyright 2014 Gabriel Bassett

 LICENSE:
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.

 DESCRIPTION:
 Functions necessary to enrich the context graph

"""
# PRE-USER SETUP
from datetime import timedelta
import logging

########### NOT USER EDITABLE ABOVE THIS POINT #################


# USER VARIABLES
CONFIG_FILE = "/tmp/verum.cfg"
LOGLEVEL = logging.INFO
LOG = None



########### NOT USER EDITABLE BELOW THIS POINT #################


## IMPORTS
import imp
import argparse
from datetime import datetime # timedelta imported above
try:
    from yapsy.PluginManager import PluginManager
    plugin_import = True
except:
    plugin_import = False
import ConfigParser
import sqlite3
import networkx as nx
import os
import urlparse  # For validate_url helper

## SETUP
__author__ = "Gabriel Bassett"
# Parse Arguments - Will overwrite Config File
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This script processes a graph.')
    parser.add_argument('-d', '--debug',
                        help='Print lots of debugging statements',
                        action="store_const", dest="loglevel", const=logging.DEBUG,
                        default=logging.WARNING
                       )
    parser.add_argument('-v', '--verbose',
                        help='Be verbose',
                        action="store_const", dest="loglevel", const=logging.INFO
                       )
    parser.add_argument('--log', help='Location of log file', default=None)
    parser.add_argument('--plugins', help="Location of plugin directory", default=None)


# Read Config File - Will overwrite file User Variables Section
log = LOG
loglevel = LOGLEVEL
try:
    config = ConfigParser.SafeConfigParser()
    config.readfp(open(CONFIG_FILE))
    config_file = True
except Exception as e:
    config_file = False
    logging.warning("Config import failed with error {0}".format(e))
# If the config file loaded...
if config_file:
    if config.has_section('Core'):
        if 'plugins' in config.options('Core'):
            PluginFolder = config.get('Core', 'plugins')
    if config.has_section('LOGGING'):
        if 'level' in config.options('LOGGING'):
            level = config.get('LOGGING', 'level')
            if level == 'debug':
                loglevel = logging.DEBUG
            elif level == 'verbose':
                loglevel = logging.INFO
            else:
                loglevel = logging.WARNING
        else:
            loglevel = logging.WARNING
        if 'log' in config.options('LOGGING'):
            log = config.get('LOGGING', 'log')
        else:
            log = None
## Set up Logging
if __name__ == "__main__":
    args = parser.parse_args()
    if args.log is not None:
        log = args.log
    if args.loglevel != logging.Warning:
        loglevel = args.loglevel
    # Get plugins folder
    if args.plugins:
        PluginFolder = args.plugins

if log:
    logging.basicConfig(filename=log, level=loglevel)
else:
    logging.basicConfig(level=loglevel)


## EXECUTION
class enrich():
    enrichment_db = None  # the sqlite database of plugins
    plugins = None  # Configured plugins
    storage = None  # The plugin to use for storage
    PluginFolder = None  # Folder where the plugins are
    score = None  # the plugin to use for scoring
    classify = None  # the clasification plugin

    def __init__(self, PluginFolder=PluginFolder):
        #global PluginFolder
        self.PluginFolder = PluginFolder

        # Load enrichments database
        self.enrichment_db = self.set_enrichment_db()

        # Load the plugins Directory
        if self.PluginFolder:
            self.load_plugins()
        else:
            logging.warning("Plugin folder not doesn't exist.  Plugins not configured.  Please run set_plugin_folder(<PluginFolder>) to set the plugin folder and then load_plugins() to load plugins.")


    ## PLUGIN FUNCTIONS

    def set_plugin_folder(self, PluginFolder):
        self.PluginFolder = PluginFolder

    def get_plugin_folder(self):
        return self.PluginFolder

    # Load the plugins from the plugin directory.
    def load_plugins(self):
        print "Configuring Plugin manager."
        self.plugins = PluginManager()
        self.plugins.setPluginPlaces([self.PluginFolder])
        #self.plugins.collectPlugins()
        self.plugins.locatePlugins()
        self.plugins.loadPlugins()
        print "Plugin manager configured."

        # Loop round the plugins and print their names.
        cur = self.enrichment_db.cursor()
        for plugin in self.plugins.getAllPlugins():
            plugin_config = plugin.plugin_object.configure()
            # Insert enrichment
            if plugin_config[0] == 'enrichment': # type
                cur.execute('''INSERT INTO enrichments VALUES (?, ?, ?, ?, ?)''', (plugin_config[2], # Name
                                                                               int(plugin_config[1]), # Enabled
                                                                               plugin_config[3], # Descripton
                                                                               plugin_config[5], # Cost
                                                                               plugin_config[6]) # Speed 
                )
                for inp in plugin_config[4]: # inputs
                    # Insert into inputs table
                    cur.execute('''INSERT INTO inputs VALUES (?,?)''', (plugin_config[2], inp))
                self.enrichment_db.commit()
            elif plugin_config[0] == 'interface': # type
                cur.execute('''INSERT INTO storage VALUES (?, ?)''', (plugin_config[2], int(plugin_config[1])))
            elif plugin_config[0] == 'score':
                cur.execute('''INSERT INTO score VALUES (?, ?, ?, ?, ?)''', (plugin_config[2], # Name
                                                                               int(plugin_config[1]), # Enabled
                                                                               plugin_config[3], # Descripton
                                                                               plugin_config[4], # Cost
                                                                               plugin_config[5]) # Speed 
                )

            if plugin.name == "classify":  # Classify is a unique name.  TODO: figure out if handling multiple 'classify' plugins is necessary
                self.classify = plugin.plugin_object

            print "Configured {2} plugin {0}.  Success: {1}".format(plugin.name, plugin_config[1], plugin_config[0])


    def set_enrichment_db(self):
        """

        Sets up the enrichment sqlite in memory database
        """
        conn = sqlite3.connect(":memory:")
        cur = conn.cursor()
        # Create enrichments table
        cur.execute('''CREATE TABLE enrichments (name text NOT NULL PRIMARY KEY,
                                               configured int,
                                               description text,
                                               cost int,
                                               speed int);''')
        # Create inputs table
        cur.execute('''CREATE TABLE inputs (name text NOT NULL,
                                          input text NOT NULL,
                                          PRIMARY KEY (name, input),
                                          FOREIGN KEY (name) REFERENCES enrichments(name));''')
        # Create interface table
        cur.execute('''CREATE TABLE storage (name text NOT NULL PRIMARY KEY,
                                             configured int
                                            );''')

        # Create storage table
        cur.execute('''CREATE TABLE score (name text NOT NULL PRIMARY KEY,
                                             configured int,
                                             description text,
                                             cost int,
                                             speed int);''')
        conn.commit()

        return conn


    ## ENRICHMENT FUNCTIONS

    def get_inputs(self):
        """ NoneType -> list of strings
        
        :return: A list of the potential enrichment inputs (ip, domain, etc)
        """
        inputs = list()
        cur = self.enrichment_db.cursor()
        for row in cur.execute('''SELECT DISTINCT input FROM inputs;'''):
            inputs.append(row[0])
        return inputs


    def get_enrichments(self, inputs, cost=10000, speed=10000, configured=True):
        """

        :param inputs: list of input types.   (e.g. ["ip", "domain"])  All enrichments that match at least 1 input type will be returned.
        :param cost:  integer 1-10 of resource cost of running the enrichment.  (1 = cheapest)
        :param speed: integer 1-10 speed of enrichment. (1 = fastest)
        :param enabled: Plugin is correctly configured.  If false, plugin may not run correctly.
        :return: list of names of enrichments matching the criteria
        """
        cur = self.enrichment_db.cursor()

        if type(inputs) == str:
            inputs = [inputs]

        plugins = list()
        names = list()
        for row in cur.execute('''SELECT DISTINCT name FROM inputs WHERE input IN ({0});'''.format(("?," * len(inputs))[:-1]), inputs):
            names.append(row[0])
        for row in cur.execute('''SELECT DISTINCT name
                                  FROM enrichments
                                  WHERE cost <= ?
                                    AND speed <= ?
                                    AND configured = ?
                                    AND name IN ({0});'''.format(("?," * len(names))[:-1]),
                                [cost,
                                 speed,
                                 int(configured)] + 
                                 names
                               ):
            plugins.append(row[0])

        return plugins


    def run_enrichments(self, topic, topic_type, names=None, cost=10, speed=10, start_time=""):
        """

        :param topic: topic to enrich (e.g. "1.1.1.1", "www.google.com")
        :param topic_type: type of topic (e.g. "ip", "domain")
        :param cost: integer 1-10 of resource cost of running the enrichment.  (1 = cheapest)
        :param speed: integer 1-10 speed of enrichment. (1 = fastest)
        :param names: a name (as string) or a list of names of enrichments to use
        :return: None if storage configured (networkx graph representing the enrichment of the topic
        """
        enrichments = self.get_enrichments([topic_type], cost, speed, configured=True)
        #print enrichments  # DEBUG
        g = nx.MultiDiGraph()

        # IF a name(s) are given, subset to them
        if names:
            enrichments = set(enrichments).intersection(set(names))

        for enrichment in enrichments:
            # get the plugin
            plugin = self.plugins.getPluginByName(enrichment)
            # run the plugin
            g2 = plugin.plugin_object.run(topic, start_time)
            # merge the graphs
            for node, props in g2.nodes(data=True):
                g.add_node(node, props)
            for edge in g2.edges(data=True):
                g.add_edge(edge[0], edge[1], attr_dict=edge[2])

        return g


    ## INTERFACE FUNCTIONS

    def get_interfaces(self, configured=None):
        """

        :return: list of strings of names of interface plugins
        """
        cur = self.enrichment_db.cursor()
        interfaces = list()

        if configured is None:
            for row in cur.execute('''SELECT DISTINCT name FROM storage;'''):
                interfaces.append(row[0])
        else:
             for row in cur.execute('''SELECT DISTINCT name from storage WHERE configured=?;''', (int(configured),)):
                interfaces.append(row[0])           
        return interfaces

    def get_default_interface(self):
        return self.storage

    def set_interface(self, interface):
        """

        :param interface: The name of the plugin to use for storage.
        Sets the storage backend to use.  It must have been configured through a plugin prior to setting.
        """
        cur = self.enrichment_db.cursor()
        configured_storage = list()
        for row in cur.execute('''SELECT DISTINCT name FROM storage WHERE configured=1;'''):
            configured_storage.append(row[0])
        if interface in configured_storage:
            self.storage = interface
        else:
            raise ValueError("Requested interface {0} not configured. Options are {1}.".format(interface, configured_storage))


    def run_query(self, topic, max_depth=4, dont_follow=['enrichment', 'classification'], storage=None):
        """

        :param storage: the storage plugin to use
        :return: a networkx subgraph surrounded around the topic 
        """
        if not storage:
            storage = self.storage
        if not storage:
            raise ValueError("No storage set.  run set_storage() to set or provide directly.  Storage must be a configured plugin.")
        else:
            # get the plugin
            plugin = self.plugins.getPluginByName(self.storage)

        return plugin.plugin_object.query(topic, max_depth=max_depth, dont_follow=dont_follow)


    def store_graph(self, g, storage=None):
        """

        :param g: a networkx graph to merge with the set storage
        """
        if not storage:
            storage = self.storage
        if not storage:
            raise ValueError("No storage set.  run set_storage() to set or provide directly.  Storage must be a configured plugin.")
        else:
            # get the plugin
            plugin = self.plugins.getPluginByName(self.storage)
            # merge the graph
            plugin.plugin_object.enrich(g)


    ## SCORE FUNCTIONS

    def get_scoring_plugins(self, cost=10000, speed=10000, names=None, configured=True):
        """

        :param cost:  integer 1-10 of resource cost of running the enrichment.  (1 = cheapest)
        :param speed: integer 1-10 speed of enrichment. (1 = fastest)
        :param enabled: Plugin is correctly configured.  If false, plugin may not run correctly.
        :return: list of names of scoring plugins matching the criteria
        """
        cur = self.enrichment_db.cursor()

        plugins = list()

        if names is None:
            for row in cur.execute('''SELECT DISTINCT name
                                      FROM score
                                      WHERE cost <= ?
                                        AND speed <= ?
                                        AND configured = ?''',
                                    [cost,
                                     speed,
                                     int(configured)]
                                   ):
                plugins.append(row[0])
        else:
            for row in cur.execute('''SELECT DISTINCT name
                                      FROM score
                                      WHERE cost <= ?
                                        AND speed <= ?
                                        AND configured = ?
                                        AND name IN ({0});'''.format(("?," * len(names))[:-1]),
                                    [cost,
                                     speed,
                                     int(configured)] + 
                                     names
                                   ):
                plugins.append(row[0])

        return plugins


    def score_subgraph(self, topic, sg, plugin_name=None):
        if plugin_name is None:
            plugin_name=self.score

        score_plugin = self.plugins.getPluginByName(plugin_name)
        return score_plugin.plugin_object.score(sg, topic)


    def set_scoring_plugin(self, plugin):
        """

        :param interface: The name of the plugin to use for storage.
        Sets the storage backend to use.  It must have been configured through a plugin prior to setting.
        """
        cur = self.enrichment_db.cursor()
        configured_scoring_plugins = list()
        for row in cur.execute('''SELECT DISTINCT name FROM score WHERE configured=1;'''):
            configured_scoring_plugins.append(row[0])
        if plugin in configured_scoring_plugins:
            self.score = plugin
        else:
            raise ValueError("Requested scoring plugin {0} is not configured. Options are {1}.".format(plugin, configured_scoring_plugins))


    def get_default_scoring_plugin(self):
        return self.score


# TODO: Move this to it's own file
'''
class helper():
    def __init__(self):
        pass

    def create_topic(self,properties, prefix=""):
        """

        :param properties: A dictionary of properties
        :param prefix: If nodes are stored with a pref
        :return: A topic graph in networkx format with one node per property

        NOTE: If multiple values of a certain type, (e.g. multiple IPs) make the value of the type
               in the dictionary a list.
        """
        g = nx.DiGraph()

        if type(properties) == dict:
            iterator = properties.iteritems()
        else:
            iterator = iter(properties)


        for key, value in iterator:
            if type(value) in (list, set, np.ndarray):
                for v in value:
                    node_uri = "{2}class=attribute&key={0}&value={1}".format(key, v, prefix)
                    g.add_node(node_uri, {
                        'class': 'attribute',
                        'key': key,
                        'value': v,
                        'uri': node_uri
                    })
            else:
                node_uri = "{2}class=attribute&key={0}&value={1}".format(key, value, prefix)
                g.add_node(node_uri, {
                    'class': 'attribute',
                    'key': key,
                    'value': value,
                    'uri': node_uri
                })

        return g


    def validate_uri(uri):
        """

        :param uri: a URI string to be validated
        :return: bool true if valid, false if not
        """
        # TODO: Validate the order properties are in (important for uri hash lookup)

        try:
            properties = urlparse.parse_qs(urlparse.urlparse(uri).query)
        except:
            return False
        if u'key' not in properties:
            return False
        elif len(properties[u'key']) != 1:
            return False
        if u'value' not in properties:
            return False
        elif len(properties[u'value']) != 1:
            return False
        if u'attribute' not in properties:
            return False
        elif len(properties[u'attribute']) != 1:
            return False
        # Nothing failed, return true
        return True
'''
