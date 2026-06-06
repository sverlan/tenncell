`default_nettype none

module logic_vector_demo #(
    parameter int DATA_WIDTH = 40,
    parameter int FRAC_BITS = 10
) (
    input logic clk,
    input logic rst,
    output logic [5:0] leds
);

function automatic logic [5:0] conv_ufixed_40_10_to_logic_6(
    input logic [39:0] value
);
    conv_ufixed_40_10_to_logic_6 = (value >>> 10);
endfunction
logic [5:0] state_leds;
logic [5:0] state_leds_next;
logic [5:0] state_leds_prod;
logic state_leds_used;

always_comb begin
    state_leds_prod = '0;
    state_leds_used = 1'b0;


    state_leds_next = state_leds;
    if (state_leds_used) begin
        state_leds_next = '0;
    end
    state_leds_next = state_leds_next + state_leds_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset leds = 62.0
        state_leds <= 6'd62;
    end else begin
        state_leds <= state_leds_next;
    end
end

assign leds = conv_ufixed_40_10_to_logic_6(state_leds);

endmodule
