import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services'/'api'))
from app import run
class WorkflowTests(unittest.TestCase):
 def test_requires_details(self): self.assertEqual(run('está ruim')['state'],'Coletar')
 def test_requires_confirmation(self): self.assertEqual(run('Meu notebook desligou antes da apresentação')['state'],'Confirmar')
 def test_creates_after_confirmation(self): self.assertTrue(run('Meu notebook desligou',True)['ticket'].startswith('INC-'))
