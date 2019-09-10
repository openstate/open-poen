#!/usr/bin/env python

import unittest

from app import app, db
from app.models import User, Project, Subproject


class TestDatabase(unittest.TestCase):
    def setUp(self):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_password_hashing(self):
        u = User(first_name='testuser')
        u.set_password('testpassword')
        self.assertFalse(u.check_password('notthetestpassword'))
        self.assertTrue(u.check_password('testpassword'))

    def test_user_project_subproject(self):
        db.session.add(User(first_name='testuser', email='testuser@example.com'))
        db.session.add(Project(name='testproject'))
        db.session.add(Subproject(name='testsubproject1'))
        db.session.add(Subproject(name='testsubproject2'))

        u = User.query.get(1)
        p = Project.query.get(1)
        s1 = Subproject.query.get(1)
        s2 = Subproject.query.get(2)

        p.users.append(u)
        self.assertEqual(p.users[0].first_name, 'testuser')
        self.assertEqual(u.projects[0].name, 'testproject')

        s1.project_id = p.id
        s2.project_id = p.id
        self.assertEqual(s1.project.name, 'testproject')
        self.assertEqual(p.subprojects[0].name, 'testsubproject1')
        self.assertEqual(p.subprojects[1].name, 'testsubproject2')
