"""Synthetic profiles only; no printer access or physical validation."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace as NS
import xml.etree.ElementTree as ET
import jinja2  # development/test dependency, not needed by the builder
import build_purge as b
import contextlib
import importlib.util
import os
from unittest import mock
import subprocess
import sys


def synthetic():
    p = json.loads((b.ROOT / 'profiles/printer.example.json').read_text())
    p['reviewed'] = True  # synthetic fixture, never emitted for a real printer
    return p


def context(p):
    runtime = dict(p, tools=b.layout(p))
    settings = {}
    states = {}
    for t in p['tools']:
        settings[t['extruder']] = dict(max_temp=290, min_extrude_temp=170, nozzle_diameter=t['nozzle_diameter'],
            filament_diameter=t['filament_diameter'], max_extrude_cross_section=.64,
            max_extrude_only_distance=50, max_extrude_only_velocity=30)
        states[t['extruder']] = dict(can_extrude=True)
    states.update({'gcode_macro _TC_PURGE_CONFIG': dict(profile=runtime),
        'toolhead': dict(homed_axes='xyz', extruder='extruder', axis_minimum=NS(x=0,y=0,z=-1), axis_maximum=NS(x=300,y=300,z=300)),
        'gcode_move': dict(extrude_factor=1,speed_factor=1,gcode_position=NS(x=0,y=0,z=5),position=NS(x=0,y=0,z=5)),
        'gcode': dict(commands={t['select_command'].split()[0]: {} for t in p['tools']}),
        'configfile': dict(settings=settings)})
    states['gcode']['commands'].update({k:{} for k in ('_TC_PURGE_RUN','_TC_PURGE_DRAW','SET_HEATER_TEMPERATURE','TEMPERATURE_WAIT')})
    return states


def render(name, p, params, printer=None):
    text = b.make_cfg(p)
    import configparser
    cfg = configparser.RawConfigParser()
    cfg.read_string(text)
    env = jinja2.Environment(block_start_string='{%',block_end_string='%}',variable_start_string='{',variable_end_string='}',undefined=jinja2.StrictUndefined)
    def error(msg):
        raise b.ProfileError(msg)
    return env.from_string(cfg['gcode_macro '+name]['gcode']).render(printer=printer or context(p),params=params,
        action_raise_error=error,action_respond_info=lambda msg:'')


class GeometryTests(unittest.TestCase):
    def test_example_remains_unreviewed(self):
        p=synthetic(); p['reviewed']=False
        self.assertFalse(b.validate(p,False)['reviewed'])
        with self.assertRaises(b.ProfileError): b.validate(p)

    def test_sparse_sorted_slots(self):
        p=synthetic(); p['tools'].reverse()
        self.assertEqual([t['id'] for t in b.layout(b.validate(p))],[0,2])

    def test_axis_x_and_y_all_points_inside(self):
        for axis in ('x','y'):
            p=synthetic(); p['axis']=axis
            if axis=='x': p['purge_area']=dict(x_min=20,x_max=280,y_min=10,y_max=24)
            for t in b.layout(b.validate(p)):
                for q in [v for s in t['strokes'] for v in s]+[t['wipe']]:
                    self.assertTrue(p['purge_area']['x_min']<=q[0]<=p['purge_area']['x_max'])
                    self.assertTrue(p['purge_area']['y_min']<=q[1]<=p['purge_area']['y_max'])

    def test_even_odd_wipe_reserved(self):
        for passes in (2,3):
            p=synthetic(); p['passes']=passes
            l=b.layout(b.validate(p))
            for t in l:
                end=t['strokes'][-1][-1][1]
                self.assertAlmostEqual(t['wipe'][1]-end,p['wipe_distance']*(1 if passes%2 else -1))

    def test_tiny_area_rejects_not_clamps(self):
        p=synthetic(); p['purge_area']['y_max']=30
        with self.assertRaises(b.ProfileError): b.validate(p)

    def test_passes_do_not_collapse_at_edge(self):
        p=synthetic(); p['purge_area']['x_max']=16
        with self.assertRaises(b.ProfileError): b.validate(p)

    def test_nominal_extrusion_scales_with_shortened_stroke(self):
        p=synthetic(); p['purge_area']['y_max']=100
        for t in b.layout(b.validate(p)):
            self.assertLess(t['stroke_length'],p['line_length'])
            self.assertAlmostEqual(t['e_per_stroke']*3.141592653589793*t['filament_diameter']**2/4,t['stroke_length']*p['purge_cross_section'])

    def test_invalid_numbers_and_unknown_keys(self):
        for value in (float('nan'),float('inf'),True,'5',None):
            p=synthetic(); p['prime_z']=value
            with self.assertRaises(b.ProfileError): b.validate(p)
        p=synthetic(); p['prim_z']=.28
        with self.assertRaises(b.ProfileError): b.validate(p)

    def test_duplicate_ids_and_extruders(self):
        for field in ('id','extruder'):
            p=synthetic(); p['tools'][1][field]=p['tools'][0][field]
            with self.assertRaises(b.ProfileError): b.validate(p)

    def test_motion_injection_rejects(self):
        for command in ('T0\nG1 Z-10','T{0}','SAVE_CONFIG','G1 X1','T0;G1 X1','T2'):
            p=synthetic(); p['tools'][0]['select_command']=command
            with self.assertRaises(b.ProfileError): b.validate(p)

    def test_flow_cross_section_and_z_reject(self):
        for field,value in [('print_speed',100),('purge_cross_section',.7),('travel_z',.1),('passes',1.5),('edge_margin',.5),('pass_spacing',.2),('schema',1.0)]:
            p=synthetic();p[field]=value
            with self.assertRaises(b.ProfileError):b.validate(p)

    def test_build_no_overwrite_and_hash_preview(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'fixture.cfg'; report=b.build(synthetic(),out)
            self.assertEqual(report['cfg_sha256'],hashlib.sha256(out.read_bytes()).hexdigest())
            ET.parse(out.with_suffix('.svg'))
            with self.assertRaises(b.ProfileError):b.build(synthetic(),out)

    def test_cli_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'synthetic.json';path.write_text('{"schema":1,"schema":1}')
            result=subprocess.run([sys.executable,str(b.ROOT/'build_purge.py'),'validate','--profile',str(path)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2);self.assertIn('duplicate JSON key',result.stderr)


class RuntimeTests(unittest.TestCase):
    def test_helpers_refuse_unreviewed_cold_invalid_or_unsafe_z(self):
        p=synthetic();p['reviewed']=False
        for helper,params in [('_TC_PURGE_RUN',dict(T='0',TEMP='230',FINAL='1')),('_TC_PURGE_DRAW',dict(T='0',FINAL='1'))]:
            with self.assertRaises(b.ProfileError):render(helper,p,params)
        p=synthetic()
        for params in (dict(T='0',TEMP='100',FINAL='1'),dict(T='1',TEMP='230',FINAL='1'),dict(T='0',TEMP='230',FINAL='2')):
            with self.assertRaises(b.ProfileError):render('_TC_PURGE_RUN',p,params)
        c=context(p);c['gcode_move']['position'].z=500
        with self.assertRaises(b.ProfileError):render('_TC_PURGE_RUN',p,dict(T='0',TEMP='230',FINAL='1'),c)

    def test_initial_last_sparse_and_unused_skipped(self):
        text=render('PRIME_LINES',synthetic(),dict(INITIAL_TOOL='0',T0_TEMP='230',T2_TEMP='230'))
        self.assertLess(text.index('_TC_PURGE_RUN T=2'),text.index('_TC_PURGE_RUN T=0'))
        text=render('PRIME_LINES',synthetic(),dict(INITIAL_TOOL='2',T2_TEMP='230'))
        self.assertNotIn('_TC_PURGE_RUN T=0',text)

    def test_all_temperatures_checked_before_output(self):
        for bad in ('-1','abc','nan','inf','290','100'):
            with self.assertRaises(b.ProfileError):render('PRIME_LINES',synthetic(),dict(INITIAL_TOOL='0',T0_TEMP='230',T2_TEMP=bad))

    def test_unknown_tool_parameter_and_typo_reject(self):
        for key in ('T1_TEMP','T2_TMEP','TOOL_TEMP'):
            with self.assertRaises(b.ProfileError):render('PRIME_LINES',synthetic(),dict(INITIAL_TOOL='0',T0_TEMP='230',**{key:'230'}))

    def test_missing_draw_helper_aborts_before_any_heat(self):
        p=synthetic();c=context(p);del c['gcode']['commands']['_TC_PURGE_DRAW']
        with self.assertRaisesRegex(b.ProfileError,'missing required helper'):
            render('PRIME_LINES',p,dict(INITIAL_TOOL='0',T0_TEMP='230'),c)

    def test_initial_id_and_temperature_reject(self):
        for initial in ('1','0.5','00','abc'):
            with self.assertRaises(b.ProfileError):render('PRIME_LINES',synthetic(),dict(INITIAL_TOOL=initial,T0_TEMP='230'))
        with self.assertRaises(b.ProfileError):render('PRIME_LINES',synthetic(),dict(INITIAL_TOOL='0'))

    def test_unhomed_unreviewed_selector_missing(self):
        p=synthetic()
        for field in ('homed','review','selector'):
            c=context(p)
            if field=='homed':c['toolhead']['homed_axes']='xy'
            if field=='review':c['gcode_macro _TC_PURGE_CONFIG']['profile']['reviewed']=False
            if field=='selector':c['gcode']['commands']={}
            with self.assertRaises(b.ProfileError):render('PRIME_LINES',p,dict(INITIAL_TOOL='0',T0_TEMP='230'),c)

    def test_firmware_nozzle_limit_retract_standby(self):
        for field,value in [('nozzle_diameter',.6),('max_extrude_cross_section',.1),('max_extrude_only_distance',.1),('max_extrude_only_velocity',1),('max_temp',100)]:
            p=synthetic();c=context(p);c['configfile']['settings']['extruder'][field]=value
            with self.assertRaises(b.ProfileError):render('PRIME_LINES',p,dict(INITIAL_TOOL='0',T0_TEMP='230'),c)

    def test_runtime_active_tool_cold_and_factors(self):
        p=synthetic()
        for field in ('tool','cold','flow','speed'):
            c=context(p)
            if field=='tool':c['toolhead']['extruder']='extruder2'
            if field=='cold':c['extruder']['can_extrude']=False
            if field=='flow':c['gcode_move']['extrude_factor']=1.1
            if field=='speed':c['gcode_move']['speed_factor']=1.1
            with self.assertRaises(b.ProfileError):render('_TC_PURGE_DRAW',p,dict(T='0',FINAL='1'),c)

    def test_runtime_offset_bounds_reject(self):
        p=synthetic()
        for axis in ('x','y','z'):
            c=context(p);setattr(c['gcode_move']['position'],axis,1000)
            with self.assertRaises(b.ProfileError):render('_TC_PURGE_DRAW',p,dict(T='0',FINAL='1'),c)

    def test_after_selection_draw_guard_and_no_old_state_restore(self):
        p=synthetic();run=render('_TC_PURGE_RUN',p,dict(T='0',TEMP='230',FINAL='1'))
        self.assertLess(run.index('T0'),run.index('_TC_PURGE_DRAW'))
        self.assertLess(run.index('TEMPERATURE_WAIT'),run.index('_TC_PURGE_DRAW'))
        cfg=b.make_cfg(p)
        self.assertNotIn('RESTORE_GCODE_STATE NAME=',cfg)
        self.assertNotIn('SET_GCODE_OFFSET',cfg)

    def test_retract_before_wipe_lift_and_explicit_exit(self):
        p=synthetic(); text=render('_TC_PURGE_DRAW',p,dict(T='0',FINAL='1'))
        i=text.index('G1 E-0.6');self.assertIn('G0 X',text[i:]);self.assertIn('G0 Z5',text[i:])
        self.assertLess(i,text.rindex('G0 Z5'))
        self.assertIn('M83',text);self.assertTrue(text.rfind('G92 E0')>text.rfind('G0 Z5'))


@unittest.skipUnless(os.environ.get('OXPLOW_KLIPPER_SOURCE'), 'Set OXPLOW_KLIPPER_SOURCE for upstream dispatch integration')
class DispatcherTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('purge_upstream_dispatch',Path(os.environ['OXPLOW_KLIPPER_SOURCE'])/'gcode.py')
        upstream=importlib.util.module_from_spec(spec);spec.loader.exec_module(upstream)
        self.upstream=upstream
        fake=mock.Mock();fake.get_start_args.return_value={}
        fake.get_reactor.return_value.mutex.return_value=contextlib.nullcontext()
        self.dispatch=upstream.GCodeDispatch(fake)
        self.p=synthetic();self.state=context(self.p);self.selected=[];self.emitted=[];self.messages=[]
        self.dispatch.register_output_handler(self.messages.append)
        for cmd in ('G0','G1','G90','M83','G92','SET_HEATER_TEMPERATURE','TEMPERATURE_WAIT'):
            self.dispatch.register_command(cmd,lambda gcmd:self.emitted.append(gcmd.get_commandline()))
        for t in self.p['tools']:
            def select(gcmd,t=t):
                self.selected.append(t['id']);self.state['toolhead']['extruder']=t['extruder']
            self.dispatch.register_command('T'+str(t['id']),select)
        for name in ('PRIME_LINES','_TC_PURGE_RUN','_TC_PURGE_DRAW'):
            def invoke(gcmd,name=name):
                try:
                    code=render(name,self.p,gcmd.get_command_parameters(),self.state)
                except b.ProfileError as e:
                    raise gcmd.error(str(e))
                self.dispatch.run_script_from_command(code)
            self.dispatch.register_command(name,invoke)
        self.dispatch._handle_ready()

    def test_full_two_tool_dispatch_has_no_unknown_command(self):
        self.dispatch.run_script('PRIME_LINES INITIAL_TOOL=0 T0_TEMP=230 T2_TEMP=230')
        self.assertEqual(self.selected,[2,0])
        self.assertEqual(self.state['toolhead']['extruder'],'extruder')
        self.assertFalse(any('Unknown command' in m for m in self.messages))
        self.assertEqual(sum(line.startswith('G1 X') for line in self.emitted),6)
        self.assertTrue(self.emitted[-1].startswith('G92 E0'))

    def test_bad_second_temperature_native_dispatch_aborts_before_commands(self):
        with self.assertRaises(self.upstream.CommandError):
            self.dispatch.run_script('PRIME_LINES INITIAL_TOOL=0 T0_TEMP=230 T2_TEMP=nan')
        self.assertEqual(self.emitted,[]);self.assertEqual(self.selected,[])


if __name__=='__main__':unittest.main()
