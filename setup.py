from setuptools import setup, find_packages

setup(
    name='kubelingo',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'pyyaml>=6.0',
        'requests>=2.31.0',
        'python-dotenv>=1.0.0',
        'pexpect>=4.8.0',
        'typer>=0.9.0',
        'rich>=13.0.0',
        'click>=8.1.0',
        'subprocess32>=3.5.4; python_version < \'3.0\'',
    ],
    entry_points={
        'console_scripts': [
            'kubelingo=kubelingo.cli:main',
        ],
    },
)

