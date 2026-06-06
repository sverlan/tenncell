`default_nettype none

module root #(
    parameter int DATA_WIDTH = 32,
    parameter int FRAC_BITS = 16
) (
    input logic clk,
    input logic rst
);


logic [31:0] state_toggle_pulse;
logic [31:0] state_toggle_pulse_next;
logic [31:0] state_toggle_pulse_prod;
logic state_toggle_pulse_used;

child child0 (
    .clk(clk),
    .rst(rst),
    .trigger(state_toggle_pulse)
);

always_comb begin
    state_toggle_pulse_prod = '0;
    state_toggle_pulse_used = 1'b0;


    state_toggle_pulse_next = state_toggle_pulse;
    if (state_toggle_pulse_used) begin
        state_toggle_pulse_next = '0;
    end
    state_toggle_pulse_next = state_toggle_pulse_next + state_toggle_pulse_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset toggle_pulse = 0.0
        state_toggle_pulse <= 32'sd0;
    end else begin
        state_toggle_pulse <= state_toggle_pulse_next;
    end
end

endmodule
