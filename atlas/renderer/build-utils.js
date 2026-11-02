"use strict";
const canvas=(w,h=w)=>{const c=document.createElement("canvas");c.width=w;c.height=h;return c;};
const image=src=>new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve(i);i.onerror=reject;i.src=src;});
