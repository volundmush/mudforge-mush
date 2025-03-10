import os
import sys
from setuptools import setup, find_packages

os.chdir(os.path.dirname(os.path.realpath(__file__)))

OS_WINDOWS = os.name == "nt"


def get_requirements():
    """
    To update the requirements for mudforge, edit the requirements.txt file.
    """
    with open("requirements.txt", "r") as f:
        req_lines = f.readlines()
    reqs = []
    for line in req_lines:
        # Avoid adding comments.
        line = line.split("#")[0].strip()
        if line:
            reqs.append(line)
    return reqs



def package_data():
    """
    By default, the distribution tools ignore all non-python files.

    Make sure we get everything.
    """
    file_set = []
    for root, dirs, files in os.walk("mudforge_mush"):
        for f in files:
            if ".git" in f.split(os.path.normpath(os.path.join(root, f))):
                # Prevent the repo from being added.
                continue
            file_name = os.path.relpath(os.path.join(root, f), "mudforge_mush")
            file_set.append(file_name)
    return file_set


# setup the package
setup(
    name="mudforge-mush",
    version="0.1",
    author="VolundMush",
    maintainer="VolundMush",
    description="A barebones framework for making modern text-based multiplayer games (MUDs, MU*).",
    license="MIT",
    packages=find_packages(),
    install_requires=get_requirements(),
    package_data={"": package_data()},
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 3 :: Only",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Topic :: Database",
        "Topic :: Education",
        "Topic :: Games/Entertainment :: Multi-User Dungeons (MUD)",
        "Topic :: Games/Entertainment :: Puzzle Games",
        "Topic :: Games/Entertainment :: Role-Playing",
        "Topic :: Games/Entertainment :: Simulation",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
    python_requires=">=3.12",
    project_urls={
        "Source": "https://github.com/volundmush/mudforge-mush",
        "Issue tracker": "https://github.com/volundmush/mudforge-mush/issues",
        "Patreon": "https://www.patreon.com/volundmush",
    },
)
