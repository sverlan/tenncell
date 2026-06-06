`default_nettype none

module root #(
    parameter int DATA_WIDTH = 32,
    parameter int FRAC_BITS = 16
) (
    input logic clk,
    input logic rst,
    output logic signed [31:0] flag
);

// _VAL_0_0 = 0.0 in fixed-point Q16.16
localparam logic signed [31:0] _VAL_0_0 = 32'sd0;
// _VAL_1_0 = 1.0 in fixed-point Q16.16
localparam logic signed [31:0] _VAL_1_0 = 32'sd65536;
logic uart0__ready;
logic uart_ready;

logic signed [31:0] state_flag;
logic signed [31:0] state_flag_next;
logic signed [31:0] state_flag_prod;

uart uart0 (
    .clk(clk),
    .ready(uart0__ready)
);

assign uart_ready = uart0__ready;

always_comb begin
    state_flag_prod = '0;

    // (uart_ready == 1) : 1 -> flag
    if ((uart_ready == 1'b1)) begin
        state_flag_prod = state_flag_prod + _VAL_1_0;
    end

    state_flag_next = '0;
    state_flag_next = state_flag_next + state_flag_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset flag = 0.0
        state_flag <= _VAL_0_0;
    end else begin
        state_flag <= state_flag_next;
    end
end

assign flag = state_flag;

endmodule
