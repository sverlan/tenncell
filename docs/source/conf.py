# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys

sys.path.insert(0, os.path.abspath("../../src/"))  # Source code dir relative to this file

project = 'TENNCell'
copyright = '2023, Sergey Verlan'
author = 'Sergey Verlan'

#version = '0.0.1'
#release = '0.0.1'

import importlib.metadata
try:
    release = importlib.metadata.version("tenncell")
except importlib.metadata.PackageNotFoundError:
    # fallback for local dev (when not installed via PDM yet)
    from nnc._version import __version__ as release

version = release  # short version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
]

templates_path = ['_templates']
exclude_patterns = []

language = 'en'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ['_static']
