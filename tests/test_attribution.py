import unittest
from attribute_resources import attribute

def event(slot='一技能',side='A',time=4.5,before='基准色',after='灰暗',eid='R1'):
 return dict(type='表盘变化',id=eid,slot=slot,side=side,start=time,before=before,after=after)
def payload(events):
 return dict(events=events,baselines={},onsetAnalysis={'candidates':[dict(id='O1',attackerCandidate='A',victim='B',start=5,end=6,frame=None,sustained=True,damageEventIds=['D1'],substitutionEvidence=[])]})
def result(events):return attribute(payload(events))['onsetAnalysis']['candidates'][0]['resourceAttribution']

class AttributionTests(unittest.TestCase):
 def test_preceding_resource(self):self.assertEqual(result([event()])['primaryResourceCandidate'],'一技能')
 def test_multiple_resources_not_unique(self):self.assertIsNone(result([event(),event('秘卷',eid='R2')])['primaryResourceCandidate'])
 def test_substitution_and_wrong_side_not_damage_source(self):self.assertEqual(result([event('替身'),event(side='B')])['candidates'],[])
 def test_recovery_not_cast(self):self.assertEqual(result([event(before='暗底黄色点缀',after='基准色')])['candidates'],[])
 def test_after_damage_not_cause(self):
  r=result([event(time=5.1)]);self.assertEqual(r['candidates'],[]);self.assertEqual(len(r['afterDamageHints']),1)
 def test_prior_chain_not_reused(self):
  r=result([event(),dict(type='血条下降',id='D0',side='B',start=4,end=4.8)])
  self.assertEqual(r['candidates'],[]);self.assertEqual(len(r['priorChainHints']),1)
 def test_ultimate_energy_change_not_unique_source(self):self.assertIsNone(result([event('奥义')])['primaryResourceCandidate'])

if __name__=='__main__':unittest.main()
