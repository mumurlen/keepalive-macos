#!/bin/sh

"""true" &&
for x in python python3 python2; do
    /usr/bin/env "$x" -V > /dev/null 2>&1 && exec /usr/bin/env "$x" "$0" "$@"
done
>&2 echo "no python interpreter found :-("
exit 1
# """

# Actually, this is python.
# Even both python2 / python3 compatible.
# But on RHEL 8 (and other) platforms,
# we cannot write a generic shebang for python,
# because we don't know which one is installed :-(

import sys
import json
import platform
import subprocess
import os
import re
import base64
import tempfile
import time
from functools import reduce

try:
    from urlparse import urljoin
    from urllib2 import urlopen
    from urllib2 import Request
    from urllib2 import URLError
    from urllib import urlretrieve
except ImportError:
    from urllib.parse import urljoin
    from urllib.request import urlopen
    from urllib.request import Request
    from urllib.error import URLError
    from urllib.request import urlretrieve

MYLINBIT = os.getenv("LMN_MYLINBIT_BASE", "https://api.linbit.com")

AUTH_URL = urljoin(MYLINBIT, "v1/login")
CONTRACT_URL = urljoin(MYLINBIT, "v1/my/contracts")
CLUSTER_URL = urljoin(MYLINBIT, "v1/my/contracts/{0}/clusters")
LICENSE_URL = urljoin(MYLINBIT, "v1/license-from-nodehash")
MYNAME = "linbit-manage-node.py"
SELF = urljoin(MYLINBIT, "public/" + MYNAME)
GPG_KEYRING_BASE = 'https://packages.linbit.com/public/'
GPG_KEYRING_DEB_NAME = 'linbit-keyring.deb'
GPG_KEYRING_RPM_NAME = 'linbit-keyring.rpm'
GPG_KEYRING_DEB = urljoin(GPG_KEYRING_BASE, GPG_KEYRING_DEB_NAME)
GPG_KEYRING_RPM = urljoin(GPG_KEYRING_BASE, GPG_KEYRING_RPM_NAME)
LINBIT_PLUGIN_BASE = "https://packages.linbit.com/public/yum-plugin/"
LINBIT_PLUGIN = urljoin(LINBIT_PLUGIN_BASE, "linbit.py")
LINBIT_PLUGIN_CONF = urljoin(LINBIT_PLUGIN_BASE, "linbit.conf")
NODE_REG_DATA = "/var/lib/drbd-support/registration.json"

REMOTEVERSION = 1
# VERSION has to be in the form "MAJOR.MINOR"
VERSION = "1.47"

# script exit codes
E_SUCC = 0
E_FAIL = 1
E_NEED_PARAMS = 2
E_WRONG_CREDS = 3
E_NO_NODES = 4


def get_input(s):
    # py2/3
    global input
    try:
        input = raw_input
    except NameError:
        pass

    return input(s)


class Distribution(object):
    # from python-lbdist/lbdist/distribution.py 1e9160e430017ba476631b8f6ddd6bf234948fed
    _pveversion = '/usr/bin/pveversion'

    def __init__(self, osreleasepath='/etc/os-release'):
        self._supported_dist_IDs = ('amzn', 'centos', 'rhel', 'rhcos', 'almalinux', 'rocky', 'debian',
                                    'ubuntu', 'xenenterprise', 'ol', 'sles', 'opensuse-leap', 'proxmox')
        self._osreleasepath = osreleasepath

        self._osrelease = {}
        self._update_osrelease()

        self._name = self._osrelease.get('ID')
        if self._name not in self._supported_dist_IDs:
            raise Exception("Could not determine distribution info")

        self._update_version()
        self._update_family()

    @property
    def osrelease(self):
        return self._osrelease

    def _update_osrelease(self):
        # gernates a slightly oppinionated osrelease dict that is similar to /etc/os-release
        # for very old distris it just sets the bare minimum to determine version and family
        osrelease = {}
        if os.path.exists(Distribution._pveversion):
            osrelease['ID'] = 'proxmox'
            osrelease['ID_LIKE'] = 'debian'
        elif os.path.exists(self._osreleasepath):
            with open(self._osreleasepath) as o:
                for line in o:
                    line = line.strip()
                    if len(line) == 0 or line[0] == '#':
                        continue
                    k, v = line.split('=')

                    if v.startswith('"') or v.startswith("'"):
                        v = v[1:-1]  # assume they are at least symmetric

                    osrelease[k] = v
            if osrelease.get('ID', '') == 'ol':  # sorry, but you really are...
                osrelease['ID_LIKE'] = 'rhel'
            elif osrelease.get('ID', '') == 'opensuse-leap':  # they have ID_LIKE="suse opensuse"
                osrelease['ID_LIKE'] = 'sles'

        # centos 6, centos first, as centos has centos-release and redhat-release
        elif os.path.exists('/etc/centos-release'):
            osrelease['ID'] = 'centos'
            osrelease['ID_LIKE'] = 'rhel'
        # rhel 6
        elif os.path.exists('/etc/redhat-release'):
            osrelease['ID'] = 'rhel'

        self._osrelease = osrelease

    def _update_version(self):
        version = None

        if self._name == 'debian':
            try:
                v = self._osrelease['VERSION']
            except KeyError:
                msg = 'No "VERSION" in your Debian {0}, are you running testing/sid?'.format(self._osreleasepath)
                raise Exception(msg)

            m = re.search(r'^\d+ \((\w+)\)$', v)
            if not m:
                raise Exception('Could not determine version information for your Debian')
            version = m.group(1)
        elif self._name == 'ubuntu':
            version = self._osrelease['VERSION_CODENAME']
        elif self._name == 'centos':
            line = ''
            with open('/etc/centos-release') as cr:
                line = cr.readline().strip()
            # .* because the nice centos people changed their string between 6 and 7 (added 'Linux')
            # and again in the middle of the 8 series (removed '(Core|Final)')
            m = re.search(r'^CentOS .* ([\d.]+)', line)
            if not m:
                raise Exception('Could not determine version information for your Centos')
            version = m.group(1)
        elif self._name == 'amzn':
            version = self._osrelease['VERSION_ID']
        elif self._name == 'almalinux':
            version = self._osrelease['VERSION_ID']
        elif self._name == 'rocky':
            version = self._osrelease['VERSION_ID']
        elif self._name == 'rhel':
            try:
                version = self._osrelease['VERSION_ID']
            except KeyError:
                line = ''
                with open('/etc/redhat-release') as cr:
                    line = cr.readline().strip()
                m = re.search(r'^Red Hat Enterprise .* ([\d.]+) \(.*\)$', line)
                if not m:
                    raise Exception('Could not determine version information for your RHEL6')
                version = m.group(1)
        elif self._name == 'rhcos':
            version = self._osrelease['VERSION_ID']
        elif self._name == 'xenenterprise':
            version = self._osrelease['VERSION_ID']
        elif self._name == 'ol':
            version = self._osrelease['VERSION_ID']
        elif self._name == 'sles' or self._name == 'opensuse-leap':
            version = self._osrelease['VERSION_ID']
        elif self._name == 'proxmox':
            version = subprocess.check_output([Distribution._pveversion]).decode().strip().split('/')[1]
            # this gave us something like 7.2-5, cut the '-' part
            version = version.split('-')[0]
        else:
            raise Exception("Could not determine version information")

        self._version = version

    def _update_family(self):
        family = None

        families = ('rhel', 'sles', 'debian')
        if self._name in families:
            family = self._name
        elif 'ID_LIKE' in self._osrelease:
            for i in self._osrelease['ID_LIKE'].split():
                if i in families:
                    family = i
                    break

        if family is None:
            raise Exception("Could not determine family for unknown distribution")
        self._family = family

    @property
    def name(self):
        return self._name

    @property
    def version(self):
        return self._version

    @property
    def family(self):
        return self._family


class LinbitDistribution(Distribution):
    def __init__(self, osreleasepath='/etc/os-release'):
        super(LinbitDistribution, self).__init__(osreleasepath)

    @property
    def repo_name(self):
        # use '{0}' instead of '{}', RHEL 6 does not handle the modern version
        if self._name in ('debian', 'ubuntu'):
            return self._version
        elif self._name in ('rhel', 'centos', 'amzn', 'almalinux', 'rocky'):
            d = 'rhel'
            if self._name == 'amzn':
                d = 'amazonlinux'

            v = self._version
            if '.' in v:
                v = v.split('.')
                v = v[0] + '.' + v[1]
            else:
                v += '.0'
            return '{0}{1}'.format(d, v)
        elif self._name in ('xenenterprise', 'ol'):
            d = self._name
            if self._name == 'xenenterprise':
                d = 'xenserver'
            v = self._version
            if '.' in v:
                v = v.split('.')[0]
            return '{0}{1}'.format(d, v)
        elif self._name == 'sles' or self._name == 'opensuse-leap':
            v = self._version
            if '.' in v:
                v = v.split('.')
                v = v[0] + '-sp' + v[1]
            # else: TODO(rck): actually I don't know how non SPx looks like
            # in the repo it is just like "sles12"
            return 'sles{0}'.format(v)
        elif self._name == 'proxmox':
            v = self._version
            if '.' in v:
                v = v.split('.')
                v = v[0]
            return 'proxmox-{0}'.format(v)
        elif self._name == 'rhcos':
            osrel_ver = self.osrelease.get('RHEL_VERSION')
            vs = {
                '4.1': '8.0',
                '4.2': '8.0',
                '4.3': '8.1',
                '4.4': '8.1',
                '4.5': '8.2',
                '4.6': '8.2',
                '4.7': '8.3',
            }
            return 'rhel{0}'.format(vs.get(self._version) or osrel_ver or '8.6')
        else:
            raise Exception("Could not determine repository information")

    def epilogue(self, with_pacemaker=False):
        # we want to support old Python, "which" is easy enough
        def is_in_path(executable):
            path = os.getenv('PATH')
            if not path:
                return False
            for p in path.split(os.path.pathsep):
                p = os.path.join(p, executable)
                if os.path.exists(p) and os.access(p, os.X_OK):
                    return True
            return False

        def get_install_tool():
            # make sure to order by preference
            if is_in_path('apt'):
                return 'apt install'
            if is_in_path('apt-get'):
                return 'apt-get install'
            if is_in_path('zypper'):
                return 'zypper install'
            if is_in_path('dnf'):
                return 'dnf install'
            if is_in_path('yum'):
                return 'yum install'
            return '<your package manager install>'

        def get_best_module():
            uname_r = os.uname()[2]
            if self._family == 'debian':
                return 'drbd-module-{0} # or drbd-dkms'.format(uname_r)
            # something bestkernelmodule should be able to handle
            # it is fine if this is something bestkernelmodule does not handle,
            # it will raise an exception and we return the default kmod-drbd
            os_release = open(self._osreleasepath)
            data = os_release.read()
            os_release.close()
            # TODO: give it a dedicated subdomain with standard port
            req = Request('http://drbd.io:3030/api/v1/best/'+uname_r, data=data.encode())
            try:
                resp = urlopen(req, timeout=5)
                best = resp.read().decode()
                # returns a file name including .rpm, split that off
                # pkgmanagers like dnf don't like extensions/look for local files,...
                return os.path.splitext(best)[0]
            except Exception:
                # sles or rhel alike:
                kmod = '<no default kernel module for your distribution>'
                if self._family == 'rhel':
                    kmod = 'kmod-drbd'
                elif self._family == 'sles':
                    kmod = 'drbd-kmp'
                return kmod

        def add_controller_satellite(tool, satellite_extra):
            return '\nIf this is an SDS controller node you might want to install:\n' \
                   '  {0} linbit-sds-controller\n' \
                   'You can configure a highly available controller later via:\n' \
                   '  https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/#s-linstor_ha\n' \
                   'If this is an SDS satellite node you might want to install:\n' \
                   '  {1} linbit-sds-satellite {2}'.format(tool, tool, satellite_extra)

        def add_pacemaker(tool):
            return '\nIf you intend to use Pacemaker you might want to install:\n' \
                   '  {0} pacemaker corosync\n'.format(tool)

        install_tool = get_install_tool()
        best_module = get_best_module()
        utils = ''
        if self._family == 'debian':
            utils = 'drbd-utils'
        elif self._family == 'sles' or self._family == 'rhel':
            utils = 'drbd-utils drbd-udev'

        dist = 'GENERIC'
        doc = 'https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/#p-administration'
        if is_in_path('oned'):
            dist = 'OpenNebula frontend'
            utils += ' linstor-opennebula'
            doc = 'https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/#ch-opennebula-linstor'
        elif self._name == 'proxmox':
            dist = 'PVE'
            best_module = 'drbd-dkms'
            utils += ' linstor-proxmox'
            doc = 'https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/#ch-proxmox-linstor'

        # keep best_module at last position, it might contain a comment section (foo # bar)
        txt = 'Looks like you executed the script on a {0} system.'.format(dist)
        if install_tool.startswith('apt'):
            txt += '\nEnter "apt update" to update your LINBIT repositories.'
        txt += add_controller_satellite(install_tool, best_module)
        txt += "\nIf you don't intend to run an SDS satellite or controller, a useful set is:"
        txt += '\n  {0}'.format(install_tool + ' ' + utils + ' ' + best_module)
        if with_pacemaker:
            txt += add_pacemaker(install_tool)
        txt += '\nFor documentation see:\n  ' + doc
        return txt

    @classmethod
    def best_drbd_kmod(cls, choices, osreleasepath='/etc/os-release', name=None, hostkernel=None):
        # choices should be kernel module packages, they are allowed to have a path prefix
        # the best matching one, or None is returned
        if not name:
            name = cls(osreleasepath)._name

        # keep as startswith, which allows forcing rhel by setting the family as name
        if not (name.startswith('rhel') or name.startswith('centos') or
                name.startswith('almalinux') or name.startswith('rocky') or
                name.startswith('sles')):
            return None

        if not hostkernel:
            hostkernel = platform.uname()[2]
        hostkernelsplit = hostkernel.replace('-', '.')
        hostkernelsplit = hostkernelsplit.split('.')[::-1]
        # strip x86, -default,... from the end
        for i, e in enumerate(hostkernelsplit):
            if e.isdigit():
                hostkernelsplit = hostkernelsplit[i:][::-1]
                break

        kmap = {}
        for c in choices:
            kpart = os.path.basename(c)
            if not (kpart.startswith('kmod-drbd') or kpart.startswith('drbd-kmp')):
                continue
            kpart = '_'.join(kpart.split('_')[1:])  # strip kmod-drbd-x.y.z_ prefix
            if name.startswith('sles') and kpart[0] == 'k':  # strip k from k4.12.14_197.29-1
                kpart = kpart[1:]

            kpart = kpart.split('-')[0]  # strip revision and everything past it
            # convert the '_' in 3.10.0_1062,
            # but only the first one as in 4.18.0_80.1.2.el8_0.x86_64
            kpart = kpart.replace('_', '.', 1)

            kps = kpart.split('.')
            # the weird stuff should now be at the end of the array (arch, el*)
            kps = list(filter(lambda a: a.isdigit(), kps))
            if len(kps) < 3:  # first 3 are the kernel
                continue
            valid = True

            for i in range(3):
                if hostkernelsplit[i] != kps[i]:
                    valid = False
                    break
            if not valid:
                continue

            kmap['.'.join(kps[3:])] = c

        hostkernelsplit = hostkernelsplit[3:]

        def kcmp(v1, v2):
            v1s, v2s = v1.split('.'), v2.split('.')
            hks = hostkernelsplit

            ml = max(len(hks), len(v1s), len(v2s))
            for lst in (v1s, v2s, hks):
                lst += [0]*(ml-len(lst))

            for i, e in enumerate(hks):
                e = int(e)
                d1 = e - int(v1s[i])
                d2 = e - int(v2s[i])
                if d1 == d2:
                    continue
                # smaller positive one
                if d1 >= 0 and d2 >= 0:
                    if d1 < d2:
                        return v1
                    else:
                        return v2
                elif d1 >= 0 and d2 < 0:
                    return v1
                elif d1 < 0 and d2 >= 0:
                    return v2
                else:  # both negative and therefore higher
                    if d1 < d2:
                        return v2
                    else:
                        return v1

            # no winner as there was no early return
            return v1

        keys = kmap.keys()
        if not keys:
            return None
        return kmap[reduce(kcmp, keys)]


# Utility Functions that might need update (e.g., if we add distro-types)
def getHostInfo():
    if platform.system() != "Linux":
        err(E_FAIL, "You have to run this script on a GNU/Linux based system")

    hostname = platform.node().strip().split('.')[0]

    # it seems really hard to get MAC addresses if you want:
    # a python only solution, e.g., no extra C code
    # no extra non-built-in modules
    # support for legacy python versions
    macs = set()
    # we are Linux-only anyways...
    CLASSNET = "/sys/class/net"
    if os.path.isdir(CLASSNET):
        for dev in os.listdir(CLASSNET):
            devpath = os.path.join(CLASSNET, dev)

            if not os.path.islink(devpath):
                continue

            with open(os.path.join(devpath, "type")) as t:
                dev_type = t.readline().strip()
                if dev_type != '1':  # this filters for example ib/lo devs
                    continue

            # try to filter non permanent interfaces
            # very old kernels do not have /sys/class/net/*/addr_assign_type
            addr_assign_path = os.path.join(devpath, "addr_assign_type")
            if os.path.isfile(addr_assign_path):
                with open(addr_assign_path) as a:
                    dev_aatype = a.readline().strip()
                    if dev_aatype != '0' and dev_aatype != '3':  # NET_ADDR_PERM/dev_set_mac_address
                        continue
            else:  # try our best to manually filter them
                if dev.startswith("vir") or \
                   dev.startswith("vnet") or \
                   dev.startswith("bond"):
                    continue

            with open(os.path.join(devpath, "address")) as addr:
                mac = addr.readline().strip()
                macs.add(mac)

    return hostname, macs


def setup_repo_config(urlhandler, dist, family, repos, free_running=False, enable_repos=None):
    """
    Asks user which repos to enable and write the correct deb/yum repository configuration.

    :param urlhandler:
    :param str dist:
    :param str family:
    :param Dict[str, Repo] repos:
    :param bool free_running:
    :param Optional[list[str]] enable_repos: list of repos to enable without asking
    :return:
    """
    # Write repository configuration
    if family == "debian":
        repo_file = "/etc/apt/sources.list.d/linbit.list"
    elif family == "rhel":
        repo_file = "/etc/yum.repos.d/linbit.repo"
    elif family == "sles":
        repo_file = "/etc/zypp/repos.d/linbit.repo"
    else:
        return err(E_FAIL, "Unknown distribution family '{}'".format(family))

    if not free_running:
        printcolour("Repository configuration:\n", GREEN)
        print("It is perfectly fine if you do not want to enable any repositories now.")
        print("The configuration for disabled repositories gets written,")
        print("but the repositories are disabled for now.")
        print("You can edit the configuration (e.g., {0}) file later to enable them.\n".format(repo_file))

    repo_content = []
    repo_names = {}
    for k in repos:
        repo_names[k] = k in enable_repos if enable_repos else free_running
    enabled = ask_enable(repo_names, free_running)
    if family == "debian":
        enabled_keys = [x for x in enabled if enabled[x]]
        disabled_keys = [x for x in enabled if not enabled[x]]
        if enabled_keys:
            repo_content.append("{u} {e} # {d}\n\n".format(
                u=repos[enabled_keys[0]].config,
                e=" ".join(enabled_keys),
                d=" ".join(disabled_keys)))

    elif family == "rhel" or family == "sles":
        for repo in repos:
            repo_content.append("[{0}]\n".format(repo))
            repo_content.append("name=LINBIT Packages for {0} - $basearch\n".format(repo))
            repo_content.append("{0}\n".format(repos[repo].config))
            repo_content.append("enabled={0}\n".format("1" if enabled.get(repo) else "0"))
            repo_content.append("gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-linbit\n")
            repo_content.append("gpgcheck=1\n")
            repo_content.append("priority=90\n")
            repo_content.append("\n")

    printcolour("Writing repository config:\n", GREEN)
    if len(repo_content) == 0:
        if not repos:
            repo_content.append("# Could not find any repositories for your distribution\n")
            repo_content.append("# Please contact support@linbit.com\n")
        else:
            repo_content.append("# Repositories found, but none enabled\n")
    success = writeFile(repo_file, repo_content, free_running=free_running)
    if success:
        OK('Repository configuration written')

    # Download yum plugin on yum based systems
    if family == "rhel":
        def is_rhelish(major):
            if dist.startswith('xenserver'):
                # xenserver 8 has rhel7 userland
                if major == 7 and dist == 'xenserver8':
                    return True
                # let's assume the other xenserver versions behave saner
                return dist == 'xenserver{}'.format(major)

            # this is the .repo_name, so we can assume major.minor for rhel
            return dist.startswith('rhel{0}.'.format(major)) \
                or dist == 'ol{}'.format(major)

        plugin_dst = '/usr/share/yum-plugins'
        final_plugin = LINBIT_PLUGIN
        if is_rhelish(6):
            final_plugin += '.6'
        elif is_rhelish(7):
            final_plugin += '.7'
        elif is_rhelish(8):
            final_plugin += '.8'
            plugin_dst = '/usr/lib/python3.6/site-packages/dnf-plugins'
        elif is_rhelish(9):
            final_plugin += '.8'  # they are compatible
            plugin_dst = '/usr/lib/python3.9/site-packages/dnf-plugins'

        printcolour("Downloading LINBIT yum plugin\n", GREEN)
        f = urlhandler.fileHandle(final_plugin)
        plugin = [pluginline for pluginline in f]
        writeFile(os.path.join(plugin_dst, 'linbit.py'), plugin,
                  showcontent=False, askforwrite=False, free_running=free_running)

        printcolour("Downloading LINBIT yum plugin config\n", GREEN)
        f = urlhandler.fileHandle(LINBIT_PLUGIN_CONF)
        cfg = [cfgline for cfgline in f]
        writeFile("/etc/yum/pluginconf.d/linbit.conf", cfg,
                  showcontent=False, askforwrite=False, free_running=free_running)

    return True


def write_proxy_license(license_blob, free_running):
    if not free_running:
        printcolour("Writing proxy license:\n", GREEN)
    lic = [x + '\n' for x in base64.b64decode(license_blob).decode('utf-8').split('\n')]
    writeFile("/etc/drbd-proxy.license", lic,
              showcontent=False, free_running=free_running)


def main():
    py_major, py_minor = sys.version_info[:2]
    if py_major < 2 or (py_major == 2 and py_minor < 6):
        warn('Your Python version ({0}.{1}) is too old, manually add your nodes via https://my.linbit.com'.format(py_major, py_minor))
        warn('If you need further help, contact us:\n')
        contactInfo('', is_issue=False)
        sys.exit(1)
    free_running = False
    proxy_only = False
    non_interactive = False
    exclude_info_only = False
    hints_only = False
    contract_id = None  # type: Optional[int]
    cluster_id = None  # type: Optional[int]
    nodehash = None  # type: Optional[str]

    # urlhandler = requestsHandler()
    urlhandler = UrllibHandler()

    if os.path.isfile(NODE_REG_DATA):
        with open(NODE_REG_DATA) as infile:
            jsondata = json.load(infile)
            nodehash = jsondata["nodehash"]

    opts = sys.argv[1:]
    for opt in opts:
        if opt == "-p":
            proxy_only = True
            sys.argv.remove("-p")
            if not nodehash:
                err(E_FAIL, 'Your node is not registered, first run this script without "-p".'
                    "\nMake sure {0} exists!".format(NODE_REG_DATA))
        elif opt == "--exclude-info":
            exclude_info_only = True
        elif opt == "--hints":
            hints_only = True

    e_user = os.getenv('LB_USERNAME', None)
    e_pwd = os.getenv('LB_PASSWORD', None)
    """
    LB_CLUSTER_ID
    -1  means create a new cluster for node
    0   append to last cluster
    >0  add the node to this cluster id
    """
    e_cluster = os.getenv('LB_CLUSTER_ID', None)
    e_contract = os.getenv('LB_CONTRACT_ID', None)
    e_no_version_check = os.getenv('LB_NO_VERSION_CHECK', None)
    """
    LB_REPOS
    Comma separated list of repo names to pre-enable, if not set all enabled, if empty all disabled.
    In non_interactive mode this also will fetch "-only" repos
    """
    e_repos = os.getenv('LB_REPOS')  # type: Optional[list[str]]
    e_repos = e_repos.split(',') if e_repos is not None else None

    e_all = bool(e_user and e_pwd and (e_cluster or e_repos))
    e_one = e_user or e_pwd or e_cluster or e_contract

    if e_one and not e_all:
        err(E_NEED_PARAMS, 'You have to set all (or none) of the required environment variables (LB_USERNAME, LB_PASSWORD, and (LB_CLUSTER_ID or LB_REPOS)')
    if e_all and proxy_only:
        err(E_FAIL, 'You are not allowed to mix "-p" and non-interactive mode')

    non_interactive = e_all
    free_running = proxy_only or non_interactive

    headers = {}

    # these defaults are weird, but that is what it was
    lbd, dist_name, dist, family, dist_version = None, '', '', False, ''
    try:
        lbd = LinbitDistribution()
        dist_name = lbd.name
        dist = lbd.repo_name
        family = lbd.family
        dist_version = lbd.version
    except Exception:
        pass  # benignly handled

    hostname, macs = getHostInfo()
    if family == "debian" and dist_name != "proxmox":
        dist = '{0}-{1}'.format(dist_name, dist_version)

    if hints_only:
        hints = lbd.epilogue(with_pacemaker=False) if lbd else "No hints for distribution"
        print(hints)
        sys.exit(0)

    if exclude_info_only:
        print_exclude_info(family, dist)
        sys.exit(0)

    if non_interactive:
        contract_id = e_contract
        cluster_id = int(e_cluster) if e_cluster is not None else None

    if len(macs) == 0:
        err(E_FAIL, "Could not detect MAC addresses of your node")

    if proxy_only:
        headers = create_headers()
        answer = urlhandler.post_license_from_nodehash(
            headers,
            mac_addresses=list(macs),
            nodehash=nodehash,
            hostname=hostname,
            contract_id=contract_id,
            cluster_id=cluster_id)
        if not answer.is_error() and answer.data().license_file_content:
            write_proxy_license(answer.data().license_file_content, free_running)
            sys.exit(0)
        err(E_FAIL, "Error acquiring proxy license: " + str(answer))
    elif not exclude_info_only:
        force_user_input = False
        print("{0} (Version: {1})".format(MYNAME, VERSION))
        if not e_no_version_check:
            checkVersion(urlhandler)

        while True:
            username = e_user
            password = e_pwd
            if not non_interactive:
                username, password = get_token(force_user_input)
            headers = create_headers(username)

            # create a first request to test UN/PWD
            if not free_running:
                print("Connecting to {0}".format(MYLINBIT))
            status, jwt_token = urlhandler.post_login_request(headers, username, password)
            if status == 401:
                msg = "Username and/or Credential are wrong"
                if non_interactive:
                    err(E_WRONG_CREDS, msg)
                else:
                    warn(msg)
                force_user_input = True
            else:
                OK("Login successful")
                headers['Authorization'] = "Bearer " + jwt_token
                break

    if not dist and not free_running:
        print("Distribution information could not be retrieved")
        contactInfo(executeCommand("uname -a"))
        print("You can still register your node, but the script will not")
        print("write a repository configuration for this node")
        cont_or_exit()
        dist = "Unknown"

    if not isRoot():
        if free_running:
            err(E_FAIL, "You have to execute this script as super user")
        print("You are not running this script as super user")
        print("")
        print("There are two choices:")
        print("-) Abort now and restart the script (please use su/sudo)")
        print("-) Continue:")
        print("  - Registration itself does not require super user permissions")
        print("  - BUT the repository configuration will only be printed")
        print("    and written to /tmp")
        print("")
        cont_or_exit()

    # XXX
    # fake redhat
    # dist = "rhel7.2"
    # family = "rhel"
    #
    # fake suse
    # dist = "sles11-sp3"
    # family = "sles"
    #
    # fake debian
    # dist = "debian-wheezy"
    # family = "debian"
    # XXX

    if contract_id is None:
        answer = urlhandler.get_request(CONTRACT_URL, headers, ContractsResponse)

        if answer.is_error():
            err(E_FAIL, answer.error_msg())

        contracts_resp = answer.data()  # type: ContractsResponse
        contracts_list = contracts_resp.list
        contract_len = len(contracts_list)
        if contract_len == 0:
            err(E_FAIL, "Sorry, but you do not have any valid contract for this credential")
        elif contract_len > 1:
            opts = {}
            for x in contracts_list:
                opts[x.id] = "{kn} {u}".format(kn=x.kind_name, u=x.support_until)
            contract_id = getOptions(opts, what="contract")
        else:
            contract_id = contracts_list[0].id

    if cluster_id is None or cluster_id in [-1, 0]:
        reg_node = urlhandler.post_is_node_registered(
            headers,
            contract_id=contract_id,
            hostname=hostname,
            mac_addresses=list(macs))
        if reg_node is None:
            ret = urlhandler.get_request(CLUSTER_URL.format(contract_id), headers, ClustersResponse)
            if ret.is_error():
                err(E_FAIL, ret.error_msg())
            clusters = ret.data()  # type: ClustersResponse
            cluster_list = clusters.list

            if non_interactive:
                if cluster_id == 0 and len(cluster_list) > 0:
                    # append to last cluster
                    cluster_id = cluster_list[len(cluster_list) - 1].id
                else:
                    # create new cluster
                    ret = urlhandler.post_create_cluster(headers, contract_id)
                    cluster_id = ret.id
            else:
                opts = {}
                cluster_id = -1
                # only ask for cluster if we have any at all
                if len(cluster_list) > 0:
                    for x in cluster_list:
                        opts[x.id] = " ".join([y.hostname for y in x.nodes]) if x.nodes else None
                    cluster_id = getOptions(opts, allow_new=True, what="cluster")
                if cluster_id == -1:
                    ret = urlhandler.post_create_cluster(headers, contract_id)
                    cluster_id = ret.id
        else:
            cluster_id = reg_node.cluster_id

    answer = urlhandler.post_register_node(
        headers,
        contract_id=contract_id,
        cluster_id=cluster_id,
        hostname=hostname,
        distribution=dist,
        mac_addresses=list(macs),
        register_version=REMOTEVERSION,
        hidden_repos=e_repos is not None)

    if answer.is_error():
        if answer.error_code() == 1100:
            err(E_NO_NODES, "Sorry, but you do not have any nodes left for this contract")
        else:
            err(E_FAIL, answer.error_msg())
    ret = answer.data()

    if not free_running:
        printcolour("Writing registration data:\n", GREEN)
    args_save = {
        "nodehash": ret.nodehash,
        "cluster_id": str(ret.cluster_id),  # stay compatible with old format
        "hostname": hostname,
        "distribution": dist,
        "mac_addresses": ",".join(macs),  # stay compatible with old format
    }
    writeFile(NODE_REG_DATA, args_save, showcontent=False,
              free_running=free_running, asjson=True)
    if dist != "Unknown" and family:
        answer = urlhandler.post_license_from_nodehash(
            headers,
            ret.nodehash,
            mac_addresses=list(macs),
            hostname=hostname,
            contract_id=contract_id,
            cluster_id=cluster_id)
        if not answer.is_error():
            write_proxy_license(answer.data().license_file_content, free_running)

        if not free_running or non_interactive:
            setup_repo_config(urlhandler, dist, family,
                              repos=ret.repos, free_running=non_interactive, enable_repos=e_repos)

        add_linbit_keyring(family, urlhandler, free_running)

        if not free_running:  # RCK THINK
            # TODO: needs detection if user enabled pacemaker repos
            lbd_epilogue = lbd.epilogue(with_pacemaker=False) if lbd else ""
            epilogue(family, dist, lbd_epilogue, urlhandler)

    if not free_running:
        OK("Congratulations! Your node was successfully configured.")
    sys.exit(0)


# Utility functions that are unlikely to require change
def checkVersion(urlhandler):
    import re
    printcolour("Checking if version is up to date\n", GREEN)
    outdated = False

    # we do not want to fail if anything is wrong here...
    try:
        f = urlhandler.fileHandle(SELF)
        selfpy = [selfline for selfline in f]
        p = re.compile(r'^VERSION.*(\d+)\.(\d+).*')

        upstream_major = sys.maxsize
        upstream_minor = 0

        for line in selfpy:
            m = p.match(line.decode('utf-8').strip())
            if m:
                upstream_major = int(m.group(1))
                upstream_minor = int(m.group(2))
                break

        v = VERSION.split('.')
        my_major = int(v[0])
        my_minor = int(v[1])

        if my_major < upstream_major:
            outdated = True
        elif my_major == upstream_major and my_minor < upstream_minor:
            outdated = True

        if outdated:
            warn("Your version is outdated")
            tmpf = tempfile.mkstemp(suffix='_' + MYNAME)[1]
            writeFile(tmpf, selfpy, showcontent=False, askforwrite=False,
                      hinttocopy=False)
            OK("New version downloaded to {0}".format(tmpf))
        else:
            OK("Your version is up to date")
    except Exception:
        warn("Version check failed, but continuing anyways")

    if outdated:
        sys.exit(0)


def _executeCommand(command):
    pyvers = sys.version_info
    if pyvers[0] == 2 and pyvers[1] == 6:
        output = subprocess.Popen(command, shell=True,
                                  stdout=subprocess.PIPE).communicate()[0]
    else:
        output = subprocess.check_output(command, shell=True)
        output = output.decode('utf-8')
    return output


# only used for commands that should never fail (e.g., uname -a), still there was a case where "lsb_release"
# was not installed on the target system.
def executeCommand(command):
    try:
        return _executeCommand(command)
    except Exception:
        err(E_FAIL, 'Is the according tool installed to execute "{0}"?'.format(command))


# content is a list of of lines
def writeFile(name, content, showcontent=True, askforwrite=True,
              free_running=False, asjson=False, hinttocopy=True):
    origname = name
    if not isRoot():
        name = os.path.join("/tmp", os.path.basename(name))

    if showcontent and not free_running:
        print("Content:")
        for line in content:
            sys.stdout.write(line)
        print("")

    if askforwrite and not free_running:
        if askYesNo("Write to file ({0})?".format(name)):
            if os.path.isfile(name):
                print("File: {0} exists".format(name))
                if not askYesNo("Overwrite file?"):
                    return False
        else:
            return False

    dirname = os.path.dirname(name)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    with open(name, "w") as outfile:
        if asjson:
            json.dump(content, outfile)
        else:
            for line in content:
                try:
                    # py 3, when it is bytes
                    line = line.decode('utf-8')
                except Exception:
                    pass
                outfile.write(line)

    if not isRoot() and hinttocopy:
        printcolour("Important: ", MAGENTA)
        print()
        print("Please review {0} and copy file to {1}".format(name, origname))

    return True


def get_token(force_user_input):
    if len(sys.argv) == 1 or force_user_input:
        import getpass
        while True:
            username = get_input("Username: ")
            if username:
                break

        while True:
            pwd = getpass.getpass("Credential (will not be echoed): ")
            if pwd:
                break
        return username.strip(), pwd.strip()
    elif len(sys.argv) == 2:
        return sys.argv[-1], ""
    return "", ""


def err(e, string):
    printcolour("ERR: ", RED)
    print(string)
    sys.exit(e)


def warn(string):
    printcolour("W: ", MAGENTA)
    print(string)


def contactInfo(args, is_issue=True):
    if is_issue:
        print("Please report this issue to:")
    print("\tdrbd-support@linbit.com")
    print("")
    print("Make sure to include the following infomation:")
    print("{0} - Version: {1}".format(os.path.basename(sys.argv[0]), VERSION))

    for fname in ('/etc/os-release', '/etc/centos-release', '/etc/redhat-release'):
        if not os.path.exists(fname):
            continue

        print('--- ' + fname + ' ' + '-' * (61-len(fname)))
        try:
            with open(fname) as o:
                MAX_READ = 1024
                c = o.read(MAX_READ)
                if o.read(1) != '':  # not done
                    print(c)  # at least print what we got
                    raise Exception('Did not reach EOF with a read of {0}'.format(MAX_READ))
                if c[-1] == '\n':  # pretty print without needing print(end=)
                    c = c[:-1]
                print(c)
        except Exception as e:
            print('Could not successfully read all of {0}:\n{1}\nPlease attach file'.format(fname, e))
        print('-' * 66)

    print(args)


def askYesNo(question):
    printcolour("--> ", CYAN)
    ret = get_input(question + " [y/N] ")
    ret = ret.strip().lower()
    if ret == 'y' or ret == "yes":
        return True
    else:
        return False


def cont_or_exit():
    if not askYesNo("Continue?"):
        sys.exit(0)


def create_headers(username=None):
    headers = {
        'Content-Type': 'application/json',
    }
    agent = "ManageNode/{0}".format(VERSION)
    if username:
        agent += " (U:{0})".format(username)
    headers['User-agent'] = agent

    return headers


def isRoot():
    return os.getuid() == 0


def getOptions(options, allow_new=False, what="contract"):
    # dicts have no guaranteed order, so we use an array to keep track of the
    # keys
    lst = []
    new = 0
    e = -1  # set it in case len(options) == 0

    print("Will this node form a cluster with...\n")
    for e, k in enumerate(sorted(options)):
        lst.append(k)
        if what == "contract":
            print("{0}) Contract: {1} (ID: {2})".format(e + 1, options[k], k))
        elif what == "cluster":
            print("{0}) Nodes: {1} (Cluster-ID: {2})".format(e + 1, options[k], k))
        else:
            err(E_FAIL, "Unknown selection option")

    if allow_new:
        printcolour("{0}) *Be first node of a new cluster*\n".format(e + 2), CYAN)
        new = 1
    print("")

    while True:
        printcolour("--> ", CYAN)
        nr = get_input("Please enter a number in range and press return: ")
        try:
            nr = int(nr.strip()) - 1  # we are back to CS/array notion
            if nr >= 0 and nr < len(options) + new:
                if allow_new and nr == e + 1:
                    return -1
                else:
                    return lst[nr]
        except ValueError:
            pass


def print_exclude_info(family, dist):
    # Print excludes information for RHEL/CENTOS users.
    if family != "rhel":
        return

    repos = ["base", "updates", "el repo (if enabled)"]
    excludes = [
        "cluster*",
        "corosync*",
        "drbd",
        "kmod-drbd",
        "libqb*",
        "pacemaker*",
        "resource-agents*",
    ]
    cent6_pluginconf_steps = ""
    if dist.startswith("rhel7"):
        repos.extend(
            ["rhel-ha-for-rhel-7-server-rpms (RHEL only)",
             "rhel-rs-for-rhel-7-server-rpms (RHEL only)"]
            )
    if dist.startswith("rhel6"):
        cent6_pluginconf_steps = (
            "and if you are using RHEL, rhel-x86_64-server-6 under "
            "/etc/yum/pluginconf.d/rhnplugin.conf")

    print("Please add the following line to your")
    print(", ".join(repos))
    print("repositories under /etc/yum.repos.d/")

    if cent6_pluginconf_steps:
        print(cent6_pluginconf_steps)

    print("to ensure you are using LINBIT's packages:")

    print("\nexclude=" + " ".join(excludes) + "\n")


# has to work on ancient python, so no shutil.which()
def which(cmd):
    return any(os.access(os.path.join(path, cmd), os.X_OK) for path in os.environ["PATH"].split(os.pathsep))


def print_yum_dnf_info(family, dist):
    if family != "rhel" or not dist.startswith("rhel7"):
        return

    if which('dnf'):
        printcolour("Please make sure to use 'yum', and *not* 'dnf' on RHEL7-alikes\n", YELLOW)


def add_linbit_keyring(family, urlhandler, free_running=False):
    if (isRoot() and
       (free_running or askYesNo("Add LINBIT signing keyring?"))):
        gpg_url, key_ring_name, addkey_cmd = None, None, None
        if family == "rhel" or family == "sles":
            gpg_url = GPG_KEYRING_RPM
            key_ring_name = GPG_KEYRING_RPM_NAME
            addkey_cmd = "rpm --replacepkgs -i {f}"
        elif family == "debian":
            gpg_url = GPG_KEYRING_DEB
            key_ring_name = GPG_KEYRING_DEB_NAME
            addkey_cmd = "dpkg -i {f}"

        if addkey_cmd and gpg_url and key_ring_name:
            tmpf = os.path.join('/tmp', key_ring_name) 
            urlretrieve(gpg_url, tmpf)
            addkey = addkey_cmd.format(f=tmpf)
            output = executeCommand(addkey)
            if (not free_running) and (output != ""):
                print(output)
    else:
        if not free_running:
            print("Download linbit-keyring.deb/rpm from {0} and install it manually!".format(GPG_KEYRING_BASE))


def epilogue(family, dist, lbd_epilogue, urlhandler):
    printcolour("Final Notes:", GREEN)
    print("")

    print_exclude_info(family, dist)
    print_yum_dnf_info(family, dist)

    if lbd_epilogue:
        print(lbd_epilogue)


class APIAnswer(object):
    def __init__(self, answer, data_type):
        self._answer = answer
        if not isinstance(answer.get('data', {}), dict):
            err(E_FAIL, "Expected object type in APIAnswer.data: " + str(answer["data"]))
        self._data_type = data_type

    def data(self):
        if 'data' in self._answer:
            return self._data_type(self._answer['data'])
        return None

    def error_msg(self):
        if self.is_error():
            return self._answer['error']['message']
        return None

    def is_error(self):
        return "error" in self._answer

    def error_code(self):
        return self._answer.get('error', {}).get('code')

    def __str__(self):
        if not self.is_error():
            return str(self._answer['data'])
        return "Error: {0}".format(self.error_msg())

    def __repr__(self):
        return "APIAnswer({0}): {1}".format(self._data_type, self._answer)


class Response(object):
    def __init__(self, response):
        self._resp = response

    def __str__(self):
        return str(self._resp)


class LoginResponse(Response):
    def __init__(self, response):
        super(LoginResponse, self).__init__(response)

    @property
    def access_token(self):
        return self._resp["access_token"]


class CreateFromNodeHashResponse(Response):
    def __init__(self, response):
        super(CreateFromNodeHashResponse, self).__init__(response)

    @property
    def license_file_content(self):
        return self._resp.get("license_file_content")


class IsNodeRegisteredResponse(Response):
    def __init__(self, response):
        super(IsNodeRegisteredResponse, self).__init__(response)

    def is_registered(self):
        return "cluster_id" in self._resp

    @property
    def cluster_id(self):
        """

        :return: cluster_id of registered node
        :rtype: int
        """
        return self._resp["cluster_id"]

    @property
    def nodehash(self):
        """

        :return: nodehash of registered node
        :rtype: str
        """
        return self._resp["nodehash"]


class Repo(Response):
    def __init__(self, response):
        super(Repo, self).__init__(response)

    @property
    def config(self):
        return self._resp["config"]


class RegisteredNodeResponse(Response):
    def __init__(self, response):
        super(RegisteredNodeResponse, self).__init__(response)

    @property
    def nodehash(self):
        return self._resp["nodehash"]

    @property
    def repo_config(self):
        return self._resp["repo_config"]

    @property
    def repos(self):
        """
        Returns possible repos from registered node.

        :return:
        :rtype: Dict[str, Repo]
        """
        reps = {}
        for k, v in self._resp["repos"].items():
            reps[k] = Repo(v)
        return reps

    @property
    def cluster_id(self):
        return self._resp["cluster_id"]


class CreateClusterResponse(Response):
    def __init__(self, response):
        super(CreateClusterResponse, self).__init__(response)

    @property
    def id(self):
        return self._resp["id"]


class Contract(Response):
    def __init__(self, response):
        super(Contract, self).__init__(response)

    @property
    def id(self):
        return self._resp["id"]

    @property
    def kind_name(self):
        return self._resp["kind_name"]

    @property
    def support_until(self):
        return self._resp["support_until"]


class ContractsResponse(Response):
    def __init__(self, response):
        super(ContractsResponse, self).__init__(response)

    @property
    def list(self):
        return [Contract(x) for x in self._resp["list"]]


class Node(Response):
    def __init__(self, response):
        super(Node, self).__init__(response)

    @property
    def hostname(self):
        return self._resp["hostname"]


class Cluster(Response):
    def __init__(self, response):
        super(Cluster, self).__init__(response)

    @property
    def id(self):
        return self._resp["id"]

    @property
    def nodes(self):
        return [Node(x) for x in self._resp["nodes"]]

    @property
    def customer_id(self):
        return self._resp["customer_id"]


class ClustersResponse(Response):
    def __init__(self, response):
        super(ClustersResponse, self).__init__(response)

    @property
    def list(self):
        return [Cluster(x) for x in self._resp["list"]]


class UrllibHandler(object):
    def __init__(self):
        pass

    @staticmethod
    def post_login_request(headers, username, password):
        payload = {"user": username, "pass": password}
        r = Request(AUTH_URL, data=json.dumps(payload).encode('utf-8'), headers=headers)
        try:
            f = urlopen(r)

            ret = f.read()
            ret = json.loads(ret)

            answer = APIAnswer(ret, LoginResponse)
            if answer.is_error():
                err(E_FAIL, "API returned error: " + answer.error_msg())
            return 200, answer.data().access_token
        except URLError as e:
            if str(e).startswith("HTTP Error 401"):
                return 401, None
            else:
                err(E_FAIL, "urllib returned: " + str(e))

    @staticmethod
    def get_request(path, headers, answer_data_type):
        """
        Does a simple GET request to the given path.

        :param str path:
        :param Dict[str, str] headers:
        :param answer_data_type: data type in APIAnswer object
        :return: ApiAnswer for successful HTTP requests, otherwise exits the script
        :rtype: APIAnswer
        """
        r = Request(path, headers=headers)
        try:
            f = urlopen(r)
            ret = f.read()
            ret = json.loads(ret)

            return APIAnswer(ret, answer_data_type)
        except URLError as e:
            if str(e).startswith("HTTP Error 401"):
                err(E_FAIL, "unauthorized")
            else:
                err(E_FAIL, "urllib returned: " + str(e))

    @staticmethod
    def post_license_from_nodehash(headers, nodehash, mac_addresses, hostname=None, contract_id=None, cluster_id=None):
        """
        Gets the license file content from nodehash and mac addresses.

        :param Dict[str, str] headers:
        :param str nodehash:
        :param List[str] mac_addresses:
        :param Optional[str] hostname:
        :param Optional[int] contract_id:
        :param Optional[int] cluster_id:
        :return:
        """
        payload = {
            "nodehash": nodehash,
            "mac_addresses": mac_addresses,
        }
        if hostname:
            payload["hostname"] = hostname
        if contract_id:
            payload["contract_id"] = int(contract_id)
        if cluster_id:
            payload["cluster_id"] = int(cluster_id)
        r = Request(LICENSE_URL, data=json.dumps(payload).encode('utf-8'), headers=headers)
        try:
            f = urlopen(r)

            ret = f.read()
            ret = json.loads(ret)

            return APIAnswer(ret, CreateFromNodeHashResponse)
        except URLError as e:
            err(E_FAIL, "Error license-from-nodehash: " + str(e))

    @staticmethod
    def post_is_node_registered(headers, contract_id, hostname, mac_addresses):
        """

        :param headers:
        :param contract_id:
        :param hostname:
        :param mac_addresses:
        :return:
        :rtype: IsNodeRegisteredResponse
        """
        payload = {
            "hostname": hostname,
            "mac_addresses": mac_addresses}
        url = urljoin(MYLINBIT, "/v1/my/contracts/{c}/is-node-registered".format(c=contract_id))
        r = Request(url,
                    data=json.dumps(payload).encode('utf-8'),
                    headers=headers)
        try:
            f = urlopen(r)
            ret = f.read()
            ret = json.loads(ret)
            answer = APIAnswer(ret, IsNodeRegisteredResponse)
            if answer.is_error():
                err(E_FAIL, answer.error_msg())
            return answer.data() if answer.data().is_registered() else None
        except URLError as e:
            err(E_FAIL, "Error is-node-registered: " + str(e))

    @staticmethod
    def post_register_node(
            headers, contract_id, cluster_id, hostname, distribution, mac_addresses, register_version, hidden_repos):
        """
        Do a POST request to the register-node endpoint.

        :param headers:
        :param contract_id:
        :param cluster_id:
        :param hostname:
        :param distribution:
        :param mac_addresses:
        :param register_version:
        :param bool hidden_repos: request hidden repos from backend
        :return: APIAnswer with RegisterNodeResponse data type
        :rtype: APIAnswer
        """
        payload = {
            "hostname": hostname,
            "distribution": distribution,
            "mac_addresses": mac_addresses,
            "register_version:": register_version,
            "hidden_repos": hidden_repos}
        url = urljoin(MYLINBIT, "v1/my/contracts/{co}/clusters/{cl}/register-node".format(
            co=contract_id, cl=cluster_id))
        r = Request(url,
                    data=json.dumps(payload).encode('utf-8'),
                    headers=headers)
        try:
            f = urlopen(r)

            ret = f.read()
            ret = json.loads(ret)
            answer = APIAnswer(ret, RegisteredNodeResponse)
            return answer
        except URLError as e:
            err(E_FAIL, "Error register-node({u}): {e}".format(u=url, e=e))

    @staticmethod
    def post_create_cluster(headers, contract_id):
        """

        :param headers:
        :param contract_id:
        :return:
        :rtype: CreateClusterResponse
        """
        payload = {}
        r = Request(CLUSTER_URL.format(contract_id), data=json.dumps(payload).encode('utf-8'), headers=headers)
        try:
            f = urlopen(r)

            ret = f.read()
            ret = json.loads(ret)
            answer = APIAnswer(ret, CreateClusterResponse)
            if answer.is_error():
                err(E_FAIL, "Error: " + answer.error_msg())
            return answer.data()
        except URLError as e:
            err(E_FAIL, "Error create-cluster: " + str(e))

    def fileHandle(self, url):
        return urlopen(url)


# following from Python cookbook, #475186
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = list(range(8))


def has_colours(stream):
    if not hasattr(stream, "isatty"):
        return False
    if not stream.isatty():
        return False  # auto color only on TTYs
    try:
        import curses
        curses.setupterm()
        return curses.tigetnum("colors") > 2
    except Exception:
        # guess false in case of error
        return False


def printcolour(text, colour=WHITE, stream=sys.stdout):
    if has_colours(stream):
        seq = "\x1b[1;{0}m{1}\x1b[0m".format(30+colour, text)
        stream.write(seq)
    else:
        stream.write(text)


def OK(text):
    sys.stdout.write('[')
    printcolour("OK", GREEN)
    sys.stdout.write('] ')
    print(text)


def ask_enable(names, free_running=False):
    """
    Asks the user which repos they wish to enable.

    :param Dict[str, bool] names: A dict of repo name keys and bool if enabled/disabled.
    :param bool free_running: indicating if there will be no user input.
    :return: An array of dicts, keys are repo names, values are True if repo is
            enabled.
    :rtype: Dict[str, bool]
    """
    repos = []
    # Sort reverse to try to show newest versions first.
    for name in sorted(names.keys(), reverse=True):
        repos.append([name, names[name]])

    # Skip asking questions in non-interacting mode.
    while not free_running:
        idx_offset = 1  # For converting between zero and one indexed arrays.
        os.system("clear")
        print("\n  Here are the repositories you can enable:\n")
        for index, repo in enumerate(repos):

            name, value = repo

            status = "Disabled"
            display_color = RED

            if value:
                status = "Enabled"
                display_color = GREEN

            printcolour(
                "    {0}) {1}({2})\n".format(index + idx_offset, name, status),
                display_color
            )

        print("\n  Enter the number of the repository you "
              "wish to enable/disable. Hit 0 when you are done.\n")
        choice = get_input("  Enable/Disable: ")

        # Ignore random button mashing.
        if not choice:
            continue

        try:
            choice = int(choice.strip())
        except ValueError:
            print("\n  You must enter a number!\n")
            time.sleep(1)
            continue

        if choice == 0:
            break

        choice_idx = choice - idx_offset
        try:
            # Toggle Enabled/Disabled
            repos[choice_idx][1] = not repos[choice_idx][1]
        except IndexError:
            # User will see if state of the repos change,
            # No need to complain.
            pass

    repo_map = {}
    for repo in repos:
        name, enabled = repo
        repo_map[name] = enabled

    return repo_map


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("")
        warn("Received Keyboard Interrupt signal, exiting...")
    except EOFError:
        print("")
        warn("Reached EOF waiting for input, exiting...")
