#!/usr/bin/env python3
from setuptools import setup, find_packages
from setuptools_rust import RustExtension
import io
import os

here = os.path.abspath(os.path.dirname(__file__))
with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='kubelingo',
    version='0.1.0',
    description='CLI quizzes for kubectl commands and Kubernetes YAML editing',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='kubelingo Contributors',
    author_email='noreply@example.com',
    url='https://github.com/your-repo/kubelingo',
    packages=find_packages(),
    include_package_data=True,
    package_data={'kubelingo': ['data/*.json']},
    install_requires=[
        'boto3>=1.26.0',
        'click>=8.0.0',
        'colorama>=0.4.4',
        'kubernetes>=25.0.0',
        'PyYAML>=6.0',
        'questionary>=1.10.0',
        'python-dotenv>=0.21.0',
        'llm>=0.14.0',
        'llm-openai>=0.5.0'
    ],
    extras_require={
        'test': [
            'pytest>=6.0',
        ],
    },
    setup_requires=['setuptools-rust'],
    rust_extensions=[
        RustExtension("kubelingo._native", "Cargo.toml", quiet=False),
    ],
    entry_points={
        'console_scripts': [
            'kubelingo=kubelingo.cli:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.8',
    zip_safe=False,
)
