"""
This setup module is only intended for use when installing Celery tasks, NOT the Django application itself.
Any interaction with the application should rely solely on the HTTP-based RESTful APIs exposed by the application.
"""
from setuptools import setup


with open('worker/README.rst') as readme, open('AUTHORS') as authors:
    long_description = '{}\n\n{}'.format(readme.read(), authors.read())

setup(
    name='edx-ecommerce-tasks',
    version='0.1.0',
    description='Celery tasks supporting the operations of edX\'s ecommerce service',
    long_description=long_description,
    classifiers=[
        'Development Status :: 1 - Planning',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet',
        'Intended Audience :: Developers',
        'Environment :: Web Environment',
    ],
    keywords='edx ecommerce tasks',
    url='https://github.com/edx/ecommerce/tree/master/worker',
    author='edX',
    author_email='oscm@edx.org',
    license='AGPL',
    packages=['worker'],
    install_requires=['Django'],
)
