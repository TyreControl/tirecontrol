import { supabase } from "./supabase";

export type UserRole = "admin" | "gerente" | "borracheiro" | "motorista" | "operador";

export type SessionProfile = {
  userId: string;
  email: string | null;
  role: UserRole;
  clienteId: string | null;
};

export async function getSessionProfile(): Promise<SessionProfile | null> {
  const { data: userData } = await supabase.auth.getUser();
  const user = userData.user;
  if (!user) return null;

  const { data: profile } = await supabase
    .from("profiles")
    .select("role, cliente_id")
    .eq("id", user.id)
    .maybeSingle();

  const role = ((profile?.role as string) || "operador").toLowerCase() as UserRole;
  return {
    userId: user.id,
    email: user.email ?? null,
    role,
    clienteId: profile?.cliente_id ?? null,
  };
}

export function canAccessGestao(role: UserRole): boolean {
  return role === "admin" || role === "gerente";
}

export function canAccessCadastroInicial(role: UserRole): boolean {
  return role === "admin" || role === "gerente" || role === "borracheiro";
}

