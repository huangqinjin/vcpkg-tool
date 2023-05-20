#!/usr/bin/env python3

import os
import re
import sys
import zipfile
import argparse
import tempfile
import subprocess
import requests


headers = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
}

def url(package, id = None):
    id = '' if id is None else f"/{id}"
    return f"https://api.github.com/user/packages/nuget/{package}/versions{id}"

def delete_version(package, version):
    if version == '0.0.0':
        print(f"Keep version 0.0.0 of {package}")
        return 0

    # https://docs.github.com/en/rest/packages?apiVersion=2022-11-28#list-package-versions-for-a-package-owned-by-the-authenticated-user
    r = requests.get(url(package), headers=headers)
    if not r.ok:
        print(f"Get versions of {package} failed")
        print(r.content)
        return -1
    
    ids = []
    num = 0
    for p in r.json():
        num += 1
        if (version is None and p['name'] != '0.0.0') or (p['name'] == version):
            ids.append(p['id'])

    if num == 0:
        print(f"Versions not found of {package}")
        return 0

    if version is not None and len(ids) != 1:
        print(f"Version {version} not found of {package}")
        return 0

    if num == 1:
        print(f"Keep at least one version of {package}")
        return 1
    
    if version is None and len(ids) == num:
        ids = ids[1:]

    for id in ids:
        # https://docs.github.com/en/rest/packages?apiVersion=2022-11-28#delete-a-package-version-for-the-authenticated-user
        r = requests.delete(url(package, id), headers=headers)
        if not r.ok:
            print(f"Delete version {id} of {package} failed")
            print(r.content)
        elif version is None:
            print(f"Delete version {id} of {package} success")
        else:
            print(f"Delete version {version} of {package} success")
    return num

def make_placeholder_version(package):
    path = os.path.join(tempfile.gettempdir(), f"{package}-0.0.0.nupkg")
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as nupkg:
        nupkg.writestr(f"{package}.nuspec", f"""\
<package>
  <metadata>
    <id>{package}</id>
    <version>0.0.0</version>
    <authors>{os.getenv('GITHUB_REPOSITORY_OWNER')}</authors>
    <requireLicenseAcceptance>false</requireLicenseAcceptance>
    <description>Placeholder Version</description>
  </metadata>
</package>
""")
    
    subprocess.run(['dotnet', 'nuget', 'push', path, '--skip-duplicate',
                    '--api-key', os.getenv('GITHUB_TOKEN'),'--source',
                    f"https://nuget.pkg.github.com/{os.getenv('GITHUB_REPOSITORY_OWNER')}/index.json"])
    os.remove(path)


def load_packages(file):
    packages={}
    with open(file) as config:
        for line in config:
            match = re.search('id="(.+)" version="(.+)"', line)
            if match:
                packages[match.group(1)] = match.group(2)
    return packages


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', help='<delete|clear|upload>')
    parser.add_argument('-p', '--package', help='list of packages or path to packages.config', nargs='+', required=True)
    parser.add_argument('-v', '--version', help='version of packages')
    parser.add_argument('-r', '--root', help='vcpkg root', default=os.getenv('VCPKG_ROOT'))

    args = parser.parse_args(argv)

    if len(args.package) == 1 and args.package[0].endswith('packages.config'):
        packages = load_packages(args.package[0])
    else:
        packages = {}
        for p in args.package:
            packages[p] = args.version

    if args.action == 'upload' and args.version == '0.0.0':
        for package, version in packages.items():
            make_placeholder_version(package)
    elif args.action == 'delete':
        for package, version in packages.items():
            delete_version(package, version)
    elif args.action == 'clear':
        for package, version in packages.items():
            while delete_version(package, None) > 1:
                pass

if __name__ == '__main__':
    main(sys.argv[1:])
