import assert from 'node:assert/strict';
import * as T from './vendor/three.module.js';
import {makeDog, makeCat, makeRabbit, makeRobot} from './model.js';
for(const [name,make] of [['dog',makeDog],['cat',makeCat],['rabbit',makeRabbit],['robot',makeRobot]]) {
 const rig=make();
 assert.ok(rig.dog.getObjectById(rig.head.id),`${name} head must be attached`);
 const tail=rig.tailBones[0].parent;tail.visible=false;
 let current=rig.head;
 while(current){assert.notEqual(current.visible,false,`${name} visible head after tail hidden`);current=current.parent;}
 rig.dog.updateMatrixWorld(true);
 const bounds=new T.Box3().setFromObject(rig.dog);
 assert.ok(!bounds.isEmpty()&&bounds.max.y>1.1,`${name} above clipping plane`);
 console.log(`PASS ${name}: attached head, visible ancestry, geometry above clipping plane`);
}
