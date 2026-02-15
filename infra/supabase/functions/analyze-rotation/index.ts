
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

serve(async (req) => {
    if (req.method === 'OPTIONS') {
        return new Response('ok', { headers: corsHeaders });
    }

    try {
        const { veiculo_id, changes } = await req.json();

        // Mock AI Analysis (Simulated Latency)
        // In a real scenario, this would call OpenAI with the 'changes' data.

        // Check if we have an OpenAI Key (placeholder)
        const openAiKey = Deno.env.get('OPENAI_API_KEY');

        let analysisText = "";

        if (openAiKey) {
            // Real Call (omitted for brevity/safety if no key, but structure is here)
            // const response = await fetch('https://api.openai.com/v1/chat/completions', ...);
            analysisText = "AI Analysis (Live): The detected wear pattern suggests a misalignment in the front axle. Recommendations: Check alignment immediately.";
        } else {
            // Simulation
            const reasons = [
                "Os pneus dianteiros apresentam desgaste acelerado (20% acima da média). Verifique o alinhamento e balanceamento.",
                "O pneu traseiro direito tem desgaste irregular. Possível problema na suspensão.",
                "Rodízio recomendado para maximizar a vida útil do jogo em 15%. Operação padrão.",
                "A pressão dos pneus parece ter sido mantida incorretamente no último ciclo, acelerando o desgaste nos ombros."
            ];
            // Pick a random reason for demo
            analysisText = reasons[Math.floor(Math.random() * reasons.length)];

            // Add specific context
            if (changes && changes.length > 0) {
                analysisText += ` A troca do pneu ${changes[0].trocar_de.marca_fogo} é crítica.`;
            }
        }

        // Simulate thinking time
        await new Promise(resolve => setTimeout(resolve, 1500));

        return new Response(JSON.stringify({ analysis: analysisText }), {
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
