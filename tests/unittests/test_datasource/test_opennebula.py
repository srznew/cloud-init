from cloudinit.sources import DataSourceOpenNebula as ds
from cloudinit import util
from mocker import MockerTestCase
from tests.unittests.helpers import populate_dir

import os

TEST_VARS = {
    'VAR1': 'single',
    'VAR2': 'double word',
    'VAR3': 'multi\nline\n',
    'VAR4': "'single'",
    'VAR5': "'double word'",
    'VAR6': "'multi\nline\n'",
    'VAR7': 'single\\t',
    'VAR8': 'double\\tword',
    'VAR9': 'multi\\t\nline\n',
    'VAR10': '\\',  # expect \
    'VAR11': '\'',  # expect '
    'VAR12': '$',   # expect $
}

USER_DATA = '#cloud-config\napt_upgrade: true'
SSH_KEY = 'ssh-rsa AAAAB3NzaC1....sIkJhq8wdX+4I3A4cYbYP ubuntu@server-460-%i'
HOSTNAME = 'foo.example.com'
PUBLIC_IP = '10.0.0.3'

CMD_IP_OUT = '''\
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 16436 qdisc noqueue state UNKNOWN
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP qlen 1000
    link/ether 02:00:0a:12:01:01 brd ff:ff:ff:ff:ff:ff
'''


class TestOpenNebulaDataSource(MockerTestCase):

    def setUp(self):
        super(TestOpenNebulaDataSource, self).setUp()
        self.tmp = self.makeDir()

    def test_seed_dir_non_contextdisk(self):
        my_d = os.path.join(self.tmp, 'non-contextdisk')
        self.assertRaises(ds.NonContextDiskDir, ds.read_context_disk_dir, my_d)

    def test_seed_dir_bad_context(self):
        my_d = os.path.join(self.tmp, 'bad-context')
        os.mkdir(my_d)
        open(os.path.join(my_d, "context.sh"), "w").close()
        self.assertRaises(ds.NonContextDiskDir, ds.read_context_disk_dir, my_d)

    def test_context_parser(self):
        my_d = os.path.join(self.tmp, 'context-parser')
        populate_context_dir(my_d, TEST_VARS)
        results = ds.read_context_disk_dir(my_d)

        self.assertTrue('metadata' in results)
        self.assertEqual(TEST_VARS, results['metadata'])

    def test_ssh_key(self):
        public_keys = ['first key', 'second key']
        for c in range(4):
            for k in ('SSH_KEY', 'SSH_PUBLIC_KEY'):
                my_d = os.path.join(self.tmp, "%s-%i" % (k, c))
                populate_context_dir(my_d, {k: '\n'.join(public_keys)})
                results = ds.read_context_disk_dir(my_d)

                self.assertTrue('metadata' in results)
                self.assertTrue('public-keys' in results['metadata'])
                self.assertEqual(public_keys,
                                 results['metadata']['public-keys'])

            public_keys.append(SSH_KEY % (c + 1,))

    def test_user_data(self):
        for k in ('USER_DATA', 'USERDATA'):
            my_d = os.path.join(self.tmp, k)
            populate_context_dir(my_d, {k: USER_DATA})
            results = ds.read_context_disk_dir(my_d)

            self.assertTrue('userdata' in results)
            self.assertEqual(USER_DATA, results['userdata'])

    def test_hostname(self):
        for k in ('HOSTNAME', 'PUBLIC_IP', 'IP_PUBLIC', 'ETH0_IP'):
            my_d = os.path.join(self.tmp, k)
            populate_context_dir(my_d, {k: PUBLIC_IP})
            results = ds.read_context_disk_dir(my_d)

            self.assertTrue('metadata' in results)
            self.assertTrue('local-hostname' in results['metadata'])
            self.assertEqual(PUBLIC_IP, results['metadata']['local-hostname'])

    def test_find_candidates(self):
        def my_devs_with(criteria):
            return {
                "LABEL=CONTEXT": ["/dev/sdb"],
                "LABEL=CDROM": ["/dev/sr0"],
                "TYPE=iso9660": ["/dev/vdb"],
            }.get(criteria, [])

        try:
            orig_find_devs_with = util.find_devs_with
            util.find_devs_with = my_devs_with
            self.assertEqual(["/dev/sdb", "/dev/sr0", "/dev/vdb"],
                             ds.find_candidate_devs())
        finally:
            util.find_devs_with = orig_find_devs_with


class TestOpenNebulaNetwork(MockerTestCase):

    def setUp(self):
        super(TestOpenNebulaNetwork, self).setUp()

    def test_lo(self):
        net = ds.OpenNebulaNetwork('', {})
        self.assertEqual(net.gen_conf(), u'''\
auto lo
iface lo inet loopback
''')

    def test_eth0(self):
        net = ds.OpenNebulaNetwork(CMD_IP_OUT, {})
        self.assertEqual(net.gen_conf(), u'''\
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet static
  address 10.18.1.1
  network 10.18.1.0
  netmask 255.255.255.0
''')

    def test_eth0_override(self):
        context = {
            'DNS': '1.2.3.8',
            'ETH0_IP': '1.2.3.4',
            'ETH0_NETWORK': '1.2.3.0',
            'ETH0_MASK': '255.255.0.0',
            'ETH0_GATEWAY': '1.2.3.5',
            'ETH0_DOMAIN': 'example.com',
            'ETH0_DNS': '1.2.3.6 1.2.3.7'
        }

        net = ds.OpenNebulaNetwork(CMD_IP_OUT, context)
        self.assertEqual(net.gen_conf(), u'''\
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet static
  address 1.2.3.4
  network 1.2.3.0
  netmask 255.255.0.0
  gateway 1.2.3.5
  dns-search example.com
  dns-nameservers 1.2.3.8 1.2.3.6 1.2.3.7
''')


def populate_context_dir(path, variables):
    data = "# Context variables generated by OpenNebula\n"
    for (k, v) in variables.iteritems():
        data += ("%s='%s'\n" % (k.upper(), v.replace(r"'", r"'\''")))
    populate_dir(path, {'context.sh': data})

# vi: ts=4 expandtab
