`default_nettype none

module inferred_ports_demo #(
    parameter int DATA_WIDTH = 8,
    parameter int FRAC_BITS = 0
) (
    input logic clk,
    input logic rst,
    input logic [7:0] sensor,
    output logic [7:0] led
);

// _VAL_0_0 = 0.0 in fixed-point Q8.0
localparam logic [7:0] _VAL_0_0 = 8'd0;
// _VAL_1_0 = 1.0 in fixed-point Q8.0
localparam logic [7:0] _VAL_1_0 = 8'd1;
logic [7:0] state_led;
logic [7:0] state_led_next;
logic [7:0] state_led_prod;

always_comb begin
    state_led_prod = '0;

    // (sensor > 0) : 1 -> led
    if ((sensor > _VAL_0_0)) begin
        state_led_prod = state_led_prod + _VAL_1_0;
    end

    state_led_next = '0;
    state_led_next = state_led_next + state_led_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset led = 0.0
        state_led <= _VAL_0_0;
    end else begin
        state_led <= state_led_next;
    end
end

assign led = state_led;

endmodule
