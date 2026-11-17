"""Synthetic checks for ROI isolation and colour-state failure boundaries."""
import unittest
import numpy as np
from analyse_color import DEFAULT,measure,state,median
from refine_onsets import locate_step,group_chains

class ColorTests(unittest.TestCase):
 def test_health_fill(self):
  hsv=np.zeros((568,1280,3),dtype=np.uint8)
  x1,y1,x2,y2=DEFAULT['hp']['A'];hsv[y1:y2,x1:(x1+x2)//2]=[5,240,220]
  self.assertAlmostEqual(measure(hsv,DEFAULT)['A_hp'],.5)
 def test_outside_hud_does_not_change_measurement(self):
  hsv=np.zeros((568,1280,3),dtype=np.uint8);before=measure(hsv,DEFAULT)
  hsv[180:]=np.random.default_rng(12).integers(0,180,hsv[180:].shape,dtype=np.uint8)
  self.assertEqual(before,measure(hsv,DEFAULT))
 def test_single_frame_flash_filtered(self):
  self.assertTrue(np.all(median(np.array([1,1,1,0,1,1,1]),5)==1))
 def test_dark_yellow_icon_is_not_automatically_cooldown(self):
  base={'dark':.34,'chroma':.36,'yellow':.03,'white':0}
  self.assertEqual(state(base,DEFAULT,base),'基准色')
 def test_relative_darkening(self):
  base={'dark':.34,'chroma':.36,'yellow':.03,'white':0}
  changed={'dark':.78,'chroma':.19,'yellow':.16,'white':0}
  self.assertEqual(state(changed,DEFAULT,base),'暗底黄色点缀')
 def test_bright_interference(self):
  m={'dark':0,'chroma':.1,'yellow':0,'white':.9}
  self.assertEqual(state(m,DEFAULT,m),'过亮')

class OnsetTests(unittest.TestCase):
 def test_exact_step_preserves_first_frame(self):
  times=np.arange(120)/60;values=np.ones(120);values[60:]=.9
  self.assertEqual(locate_step(times,values,1,172)['index'],60)
 def test_transient_flash_is_not_first_damage(self):
  times=np.arange(120)/60;values=np.ones(120);values[42:44]=.5;values[60:]=.9
  self.assertEqual(locate_step(times,values,1,172)['index'],60)
 def test_flat_health_has_no_onset(self):
  self.assertIsNone(locate_step(np.arange(120)/60,np.ones(120),1,172))
 def test_combo_hits_merge(self):
  damages=[{'side':'B','start':5,'end':5.5},{'side':'B','start':6,'end':6.5}]
  self.assertEqual(len(group_chains(damages,[])),1)
 def test_substitution_or_other_side_damage_splits_chain(self):
  damages=[{'side':'B','start':5,'end':5.5},{'side':'B','start':6,'end':6.5}]
  self.assertEqual(len(group_chains(damages,[{'side':'B','start':5.8}])),2)
  damages.insert(1,{'side':'A','start':5.7,'end':5.8})
  self.assertEqual(len(group_chains(damages,[])),3)

if __name__=='__main__':unittest.main()
