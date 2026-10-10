`default_nettype none

module root #(
    parameter int DATA_WIDTH = 40,
    parameter int FRAC_BITS = 10
) (
    input logic clk,
    input logic rst,
    input logic led
);

// _VAL_0_0 = 0.0 in fixed-point Q30.10
localparam logic [39:0] _VAL_0_0 = 40'd0;
function automatic logic signed [31:0] conv_logic_to_logic_32(
    input logic value
);
    conv_logic_to_logic_32 = value;
endfunction

logic [39:0] state_x;
logic [39:0] state_x_next;
logic [39:0] state_x_prod;
logic state_x_used;

child child0 (
    .clk(clk),
    .rst(rst),
    .sig(conv_logic_to_logic_32(led))
);

always_comb begin
    state_x_prod = '0;
    state_x_used = 1'b0;


    state_x_next = state_x;
    if (state_x_used) begin
        state_x_next = '0;
    end
    state_x_next = state_x_next + state_x_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset x = 0.0
        state_x <= _VAL_0_0;
    end else begin
        state_x <= state_x_next;
    end
end

endmodule
