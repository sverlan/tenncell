`default_nettype none

module logic_vectors_demo #(
    parameter int DATA_WIDTH = 40,
    parameter int FRAC_BITS = 10
) (
    input logic clk,
    input logic rst,
    output logic [3:0] leds4,
    output logic [5:0] leds6
);

function automatic logic [3:0] conv_ufixed_40_10_to_logic_4(
    input logic [39:0] value
);
    conv_ufixed_40_10_to_logic_4 = (value >>> 10);
endfunction

function automatic logic [5:0] conv_ufixed_40_10_to_logic_6(
    input logic [39:0] value
);
    conv_ufixed_40_10_to_logic_6 = (value >>> 10);
endfunction
logic [3:0] state_leds4;
logic [3:0] state_leds4_next;
logic [3:0] state_leds4_prod;
logic state_leds4_used;
logic [5:0] state_leds6;
logic [5:0] state_leds6_next;
logic [5:0] state_leds6_prod;
logic state_leds6_used;

always_comb begin
    state_leds4_prod = '0;
    state_leds4_used = 1'b0;
    state_leds6_prod = '0;
    state_leds6_used = 1'b0;


    state_leds4_next = state_leds4;
    if (state_leds4_used) begin
        state_leds4_next = '0;
    end
    state_leds4_next = state_leds4_next + state_leds4_prod;
    state_leds6_next = state_leds6;
    if (state_leds6_used) begin
        state_leds6_next = '0;
    end
    state_leds6_next = state_leds6_next + state_leds6_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset leds4 = 14.0
        state_leds4 <= 4'd14;
        // reset leds6 = 62.0
        state_leds6 <= 6'd62;
    end else begin
        state_leds4 <= state_leds4_next;
        state_leds6 <= state_leds6_next;
    end
end

assign leds4 = conv_ufixed_40_10_to_logic_4(state_leds4);
assign leds6 = conv_ufixed_40_10_to_logic_6(state_leds6);

endmodule
