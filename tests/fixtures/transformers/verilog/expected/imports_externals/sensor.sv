`default_nettype none

module sensor #(
    parameter int DATA_WIDTH = 24,
    parameter int FRAC_BITS = 8
) (
    input logic clk,
    input logic rst,
    output logic signed [23:0] level
);

function automatic logic [23:0] conv_sfixed_24_8_to_logic_24(
    input logic signed [23:0] value
);
    conv_sfixed_24_8_to_logic_24 = (value >>> 8);
endfunction
logic signed [23:0] state_level;
logic signed [23:0] state_level_next;
logic signed [23:0] state_level_prod;
logic state_level_used;

always_comb begin
    state_level_prod = '0;
    state_level_used = 1'b0;


    state_level_next = state_level;
    if (state_level_used) begin
        state_level_next = '0;
    end
    state_level_next = state_level_next + state_level_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset level = 3.0
        state_level <= 24'sd768;
    end else begin
        state_level <= state_level_next;
    end
end

assign level = conv_sfixed_24_8_to_logic_24(state_level);

endmodule