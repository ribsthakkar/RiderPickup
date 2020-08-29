from setuptools import setup

# https://setuptools.readthedocs.io/en/latest/setuptools.html#developer-s-guide

setup(
    name="Avicena",
    version="0.1",
    packages=['avicena'],
    #scripts=["say_hello.py"],
    #scripts=["say_hello.py"],
    entry_points={
        "console_scripts": [
            "avi-import = avicena.prepare_database:avicena_import_db",
            "avi-cli = avicena.app.run_cli:avicena_run_cli"
        ]
    },

    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    #install_requires=["docutils>=0.3"],

    #package_data={
    #    # If any package contains *.txt or *.rst files, include them:
    #    "": ["*.txt", "*.rst"],
    #    # And include any *.msg files found in the "hello" package, too:
    #    "hello": ["*.msg"],
    #},

    # metadata to display on PyPI
    #author="Me",
    #author_email="me@example.com",
    description="A project to solve the Vehicle Routing Problem (VRP)",
    keywords="vrp ml ai optimization",
    #url="http://example.com/HelloWorld/",   # project home page, if any
    #project_urls={
    #    "Bug Tracker": "https://bugs.example.com/HelloWorld/",
    #    "Documentation": "https://docs.example.com/HelloWorld/",
    #    "Source Code": "https://code.example.com/HelloWorld/",
    #},
    classifiers=[
        "License :: MIT"
    ]

    # could also include long_description, download_url, etc.
)
