/** 认证状态:token/user 持久化于 localStorage */
import { defineStore } from "pinia";
import * as api from "../api";
import { useMarketStore } from "./market";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem("fin_token") || "",
    user: JSON.parse(localStorage.getItem("fin_user") || "null"),
  }),
  getters: {
    isLoggedIn: (s) => Boolean(s.token),
    username: (s) => s.user?.username || "",
  },
  actions: {
    _persist(token, user) {
      this.token = token || "";
      this.user = user || null;
      if (token) localStorage.setItem("fin_token", token);
      else localStorage.removeItem("fin_token");
      if (user) localStorage.setItem("fin_user", JSON.stringify(user));
      else localStorage.removeItem("fin_user");
      useMarketStore().resetUserState();
    },
    async login(username, password) {
      const data = await api.authLogin({ username, password });
      this._persist(data.token, data.user);
      return data;
    },
    async register(payload) {
      const data = await api.authRegister(payload);
      this._persist(data.token, data.user);
      return data;
    },
    logout() {
      this._persist("", null);
    },
  },
});
