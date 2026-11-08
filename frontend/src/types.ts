export type Settings = {width:number;height:number;thickness:number;kerf:number;gap:number;margin:number;units:'mm'|'cm'|'m'|'in';rotate:boolean}
export type Piece = {id:string;rings:[number,number][][];label:[number,number];area:number;angle:number}
export type Sheet = {index:number;pieces:Piece[];utilization:number}
export type Job = {id:string;filename:string;settings:Settings;sheets:Sheet[];preview:{vertices:number[];faces:number[];bounds:number[]};warnings:string[];piece_count:number;utilization:number;area_mm2:number}
export type User = {name:string;email:string}
export const defaults: Settings = {width:600,height:400,thickness:3,kerf:0.15,gap:3,margin:5,units:'mm',rotate:true}
