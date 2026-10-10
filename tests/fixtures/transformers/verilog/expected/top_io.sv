`default_nettype none

module top_io_demo #(
    parameter int DATA_WIDTH = 32,
    parameter int FRAC_BITS = 16
) (
    input logic clk,
    input logic rst,
    input logic [7:0] sample,
    output logic [7:0] alarm
);

logic [7:0] state_alarm;
logic [7:0] state_alarm_next;
logic [7:0] state_alarm_prod;
logic state_alarm_used;

always_comb begin
    state_alarm_prod = '0;
    state_alarm_used = 1'b0;

    // True : (sample + 1.5) -> alarm
    if (1'b1) begin
        state_alarm_prod = state_alarm_prod + (sample + 8'd2);
    end

    state_alarm_next = state_alarm;
    if (state_alarm_used) begin
        state_alarm_next = '0;
    end
    state_alarm_next = state_alarm_next + state_alarm_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset alarm = 0.0
        state_alarm <= 8'd0;
    end else begin
        state_alarm <= state_alarm_next;
    end
end

assign alarm = state_alarm;

endmodule
