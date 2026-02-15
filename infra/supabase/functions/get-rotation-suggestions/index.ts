
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  try {
    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_ANON_KEY') ?? '',
      { global: { headers: { Authorization: req.headers.get('Authorization')! } } }
    );

    const { veiculo_id } = await req.json();

    if (!veiculo_id) {
        throw new Error("veiculo_id is required");
    }

    // 1. Get active tires on the truck
    const { data: activeTires, error: activeError } = await supabaseClient
      .from('pneus')
      .select('id, marca_fogo, km_vida_total, posicao_atual, ciclo_atual, status')
      .eq('caminhao_atual_id', veiculo_id)
      .eq('status', 'MONTADO');

    if (activeError) throw activeError;

    // 2. Get stock tires (potential replacements)
    const { data: stockTires, error: stockError } = await supabaseClient
      .from('pneus')
      .select('id, marca_fogo, km_vida_total, ciclo_atual, status')
      .eq('status', 'ESTOQUE');

    if (stockError) throw stockError;

    if (!activeTires || activeTires.length === 0 || !stockTires || stockTires.length === 0) {
        return new Response(JSON.stringify({ suggestions: [] }), {
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
            status: 200,
        });
    }

    // 3. Calculate Wear Score
    // Logic from legacy: limit = 70000 if cycle > 0 else 100000
    // Score = (km_life / limit) * 100
    const calcScore = (pneu: any) => {
        const limit = pneu.ciclo_atual > 0 ? 70000 : 100000;
        return (pneu.km_vida_total / limit) * 100;
    };

    const activeWithScore = activeTires.map((p) => ({ ...p, wear_score: calcScore(p) }));
    const stockWithScore = stockTires.map((p) => ({ ...p, wear_score: calcScore(p) }));

    // 4. Find optimal swaps
    // Sort active tires by wear (descending) - most worn first
    activeWithScore.sort((a, b) => b.wear_score - a.wear_score);

    const suggestions = [];
    // Only consider replacing the top 2 most worn tires (as per legacy logic)
    // Or we can be smarter, but let's stick to legacy for parity first.
    // Legacy logic: finds a stock tire with LOWER wear score.

    for (const activeTire of activeWithScore.slice(0, 2)) {
        // Find best stock replacement (lowest wear score)
        // Optimization: pick the one with the lowest score generally to maximize fresh rubber?
        // Legacy: finds *any* stock tire with lower score. Let's pick the *best* (lowest score).
        
        let bestReplacement = null;
        let bestEconomy = -1;

        for (const stockTire of stockWithScore) {
            // Skip tires already suggested
            if (suggestions.some(s => s.trocar_para.id === stockTire.id)) continue;

             if (stockTire.wear_score < activeTire.wear_score) {
                 const economy = activeTire.wear_score - stockTire.wear_score;
                 // We want the biggest difference (economy)
                 if (economy > bestEconomy) {
                     bestEconomy = economy;
                     bestReplacement = stockTire;
                 }
             }
        }

        if (bestReplacement) {
            suggestions.push({
                trocar_de: activeTire,
                trocar_para: bestReplacement,
                economia_percentual: bestEconomy,
                reason: `Tire ${activeTire.marca_fogo} is ${activeTire.wear_score.toFixed(1)}% worn. Replacing with ${bestReplacement.marca_fogo} (${bestReplacement.wear_score.toFixed(1)}% worn) saves ${bestEconomy.toFixed(1)}% wear.`
            });
        }
    }

    return new Response(JSON.stringify({ suggestions }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 200,
    });

  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 400,
    });
  }
});
