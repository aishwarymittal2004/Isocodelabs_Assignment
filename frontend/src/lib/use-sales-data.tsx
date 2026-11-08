import {useEffect,useState} from 'react';
import {useSalesAuth} from './sales-auth';
export function useSalesData<T>(fetcher:(token:string)=>Promise<T>, deps:readonly unknown[]=[]){
 const {token}=useSalesAuth();const [data,setData]=useState<T|null>(null);const [error,setError]=useState('');const [loading,setLoading]=useState(true);const [revision,setRevision]=useState(0);
 useEffect(()=>{let active=true;setLoading(true);setError('');fetcher(token).then(v=>{if(active)setData(v)}).catch(e=>{if(active)setError(e.message||'Unable to load data')}).finally(()=>{if(active)setLoading(false)});return()=>{active=false};},[token,revision,...deps]);
 return {data,error,loading,reload:()=>setRevision(v=>v+1)};
}
export function DataState({loading,error,retry}:{loading:boolean;error:string;retry:()=>void}){if(loading)return <div className="card-surface p-8 text-muted-foreground" role="status">Loading live records…</div>;if(error)return <div role="alert" className="card-surface p-8"><p>{error}</p><button className="btn btn-primary mt-3" onClick={retry}>Try again</button></div>;return null;}
