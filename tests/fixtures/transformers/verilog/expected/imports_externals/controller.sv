`default_nettype none

module controller_top #(
    parameter int DATA_WIDTH = 32,
    parameter int FRAC_BITS = 16
) (
    input logic clk,
    input logic rst,
    input logic uart_rx,
    output logic signed [31:0] alarm
);

// _VAL_1_0_Q16_8 = 1.0 in fixed-point Q16.8
localparam logic signed [23:0] _VAL_1_0_Q16_8 = 24'sd256;
function automatic logic signed [31:0] conv_logic_8_to_logic_32(
    input logic [7:0] value
);
    conv_logic_8_to_logic_32 = value;
endfunction
logic signed [23:0] sensor0__level;

logic [7:0] uart0__rx_data;
logic uart0__rx_valid;
logic [7:0] uart_rx_data;
logic uart_rx_valid;

logic signed [31:0] state_alarm;
logic signed [31:0] state_alarm_next;
logic signed [31:0] state_alarm_prod;
logic state_alarm_used;

sensor sensor0 (
    .clk(clk),
    .rst(rst),
    .level(sensor0__level)
);

uart uart0 (
    .clk(clk),
    .rst(rst),
    .rx(uart_rx),
    .rx_data(uart0__rx_data),
    .rx_valid(uart0__rx_valid)
);

assign uart_rx_data = uart0__rx_data;
assign uart_rx_valid = uart0__rx_valid;

always_comb begin
    state_alarm_prod = '0;
    state_alarm_used = 1'b0;

    // ((sensor0.level > 1) && (uart_rx_valid == 1)) : (uart_rx_data + 1) -> alarm
    if (((sensor0__level > _VAL_1_0_Q16_8) && (uart_rx_valid == 1'b1))) begin
        state_alarm_prod = state_alarm_prod + (conv_logic_8_to_logic_32(uart_rx_data) + 32'sd1);
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
        state_alarm <= 32'sd0;
    end else begin
        state_alarm <= state_alarm_next;
    end
end

assign alarm = state_alarm;

endmodule
