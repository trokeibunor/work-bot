export interface CandidateProfile {
  name: string; headline: string; location: string; summary: string; preferences: string
  contact: {email:string;phone:string;portfolio:string;linkedin:string;github:string}
  skills:string[]
  experience:{company:string;role:string;period:string;highlights:string[]}[]
  education:{degree:string;institution:string;period:string}[]
  projects:{name:string;role:string;period:string;problem:string;contribution:string;technologies:string[];outcomes:string[];url:string}[]
}
export interface CandidateSource {
  id:string;kind:string;title:string;status:string;raw_text:string;error?:string
  base_version_id:string;approved_version_id?:string;created_at:string;updated_at:string
  proposal?:{profile:CandidateProfile;warnings:string[];questions:string[]}
}
export interface CandidateWorkspace {
  version_id:string;profile:CandidateProfile;master_resume:string
  sources:CandidateSource[];versions:{id:string;name:string;created_at:string}[]
  capabilities:{extraction:boolean;voice:boolean}
}
