import { ComponentType, ReactNode } from "react";

export interface Toaster {
  toast(opts: { title: string; body?: string }): void;
}

export interface ServerAPI {
  callPluginMethod<TReq, TRes>(method: string, data: TReq): Promise<{ success: boolean; result: TRes }>;
  toaster: Toaster;
}

export const ButtonItem: ComponentType<any>;
export const Field: ComponentType<any>;
export const PanelSection: ComponentType<any>;
export const PanelSectionRow: ComponentType<any>;
export const SliderField: ComponentType<any>;
export const SteamSpinner: ComponentType<any>;
export const TextField: ComponentType<any>;

export const definePlugin: (
  init: (serverAPI: ServerAPI) => { title: string; content: ReactNode; icon: string }
) => any;
