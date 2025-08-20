import React, { createContext, useContext, useEffect, useState } from 'react';
import { User, Session } from '@supabase/supabase-js';
import { supabase } from '@/integrations/supabase/client';

interface AuthContextType {
  user: User | null;
  session: Session | null;
  profile: any | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<{ error: any }>;
  signUp: (email: string, password: string, fullName: string, companyName: string) => Promise<{ error: any }>;
  signOut: () => Promise<void>;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchProfile = async (userId: string) => {
    const { data, error } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', userId)
      .single();
    
    if (data && !error) {
      setProfile(data);
    }
  };

  useEffect(() => {
    // Set up auth state listener FIRST
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        setSession(session);
        setUser(session?.user ?? null);
        
        // Defer profile fetching to avoid deadlock
        if (session?.user) {
          setTimeout(() => {
            fetchProfile(session.user.id);
          }, 0);
        } else {
          setProfile(null);
        }
        
        setLoading(false);
      }
    );

    // THEN check for existing session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      
      if (session?.user) {
        setTimeout(() => {
          fetchProfile(session.user.id);
        }, 0);
      }
      
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    return { error };
  };

  const signUp = async (email: string, password: string, fullName: string, companyName: string) => {
    try {
      // Gerar UUID para a conta
      const accountId = crypto.randomUUID();
      
      console.log('Tentando criar conta:', { accountId, companyName });
      
      // Criar conta no endpoint externo
      const accountResponse = await fetch('https://atendimento.pluggerbi.com/accounts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id: accountId,
          name: companyName,
        }),
      });

      console.log('Response status:', accountResponse.status);
      
      if (!accountResponse.ok) {
        const errorText = await accountResponse.text();
        console.error('Erro na resposta do servidor:', errorText);
        throw new Error(`Erro ao criar conta da empresa: ${accountResponse.status}`);
      }

      console.log('Conta criada com sucesso, criando usuário no Supabase...');

      // Criar usuário no Supabase
      const redirectUrl = `${window.location.origin}/`;
      
      const { error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo: redirectUrl,
          data: {
            full_name: fullName,
            role: 'admin',
            account_id: accountId,
          },
        },
      });
      
      if (error) {
        console.error('Erro ao criar usuário no Supabase:', error);
      }
      
      return { error };
    } catch (err: any) {
      console.error('Erro geral:', err);
      return { error: { message: err.message || 'Erro ao criar conta. Verifique sua conexão e tente novamente.' } };
    }
  };

  const signOut = async () => {
    try {
      const { error } = await supabase.auth.signOut();
      
      // Sempre limpa o estado local, independente se há erro no servidor
      // Isso garante que o usuário seja deslogado mesmo se a sessão já expirou
      setUser(null);
      setSession(null);
      setProfile(null);
      
      if (error && error.message !== 'Session from session_id claim in JWT does not exist') {
        console.warn('Erro durante logout (mas estado foi limpo):', error.message);
      }
    } catch (err) {
      console.error('Erro ao fazer logout:', err);
      // Mesmo com erro, limpa o estado local para garantir que o usuário seja deslogado
      setUser(null);
      setSession(null);
      setProfile(null);
    }
  };

  const isAdmin = profile?.role === 'admin';

  const value = {
    user,
    session,
    profile,
    loading,
    signIn,
    signUp,
    signOut,
    isAdmin,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};