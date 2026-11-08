import { createContext, useContext } from "react";
export type SalesIdentity={id:string;display_name:string;email:string;role:'sales_head'|'sales'};
export const SalesAuthContext=createContext<{token:string;user:SalesIdentity;logout:()=>void}|null>(null);
export function useSalesAuth(){const value=useContext(SalesAuthContext);if(!value)throw new Error('Sales session required');return value;}
