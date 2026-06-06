`default_nettype none

module fpga_blink_uart #(
    parameter int DATA_WIDTH = 40,
    parameter int FRAC_BITS = 10
) (
    input logic clk,
    input logic rst,
    output logic led,
    output logic uart_tx
);

// BLINK_DELAY = 27000000.0 in fixed-point Q30.10
localparam logic [39:0] BLINK_DELAY = 40'd27648000000;

// _VAL_0_0 = 0.0 in fixed-point Q30.10
localparam logic [39:0] _VAL_0_0 = 40'd0;
// _VAL_1_0 = 1.0 in fixed-point Q30.10
localparam logic [39:0] _VAL_1_0 = 40'd1024;
// _VAL_27000000_0 = 27000000.0 in fixed-point Q30.10
localparam logic [39:0] _VAL_27000000_0 = 40'd27648000000;
function automatic logic conv_ufixed_40_10_to_logic(
    input logic [39:0] value
);
    conv_ufixed_40_10_to_logic = (value != '0);
endfunction
logic [7:0] txdrv0__tx_data;
logic txdrv0__tx_valid;
logic [7:0] tx_data;
logic tx_valid;

logic uart_tx0__ready;
logic uart_tx0__tx;
logic uart_tx0__busy;
logic uart_ready;

logic [39:0] state_counter;
logic [39:0] state_counter_next;
logic [39:0] state_counter_prod;
logic state_led;
logic state_led_next;
logic state_led_prod;
logic state_toggle_pulse;
logic state_toggle_pulse_next;
logic state_toggle_pulse_prod;

blink_uart_tx_driver txdrv0 (
    .clk(clk),
    .rst(rst),
    .trigger(state_toggle_pulse),
    .led_state(led),
    .uart_ready(uart_ready),
    .tx_data(txdrv0__tx_data),
    .tx_valid(txdrv0__tx_valid)
);

uart_tx #(.CLOCK_HZ(27000000), .BAUD_RATE(115200)) uart_tx0 (
    .clk(clk),
    .rst(rst),
    .data_in(tx_data),
    .valid(tx_valid),
    .ready(uart_tx0__ready),
    .tx(uart_tx0__tx),
    .busy(uart_tx0__busy)
);

assign tx_data = txdrv0__tx_data;
assign tx_valid = txdrv0__tx_valid;

assign uart_ready = uart_tx0__ready;

always_comb begin
    state_counter_prod = '0;
    state_led_prod = '0;
    state_toggle_pulse_prod = '0;

    // (counter < 27000000) : (counter + 1) -> counter
    if ((state_counter < _VAL_27000000_0)) begin
        state_counter_prod = state_counter_prod + (state_counter + _VAL_1_0);
    end
    // (counter < 27000000) : led -> led
    if ((state_counter < _VAL_27000000_0)) begin
        state_led_prod = state_led_prod + state_led;
    end
    // ((counter >= 27000000) && (uart_ready == 0)) : counter -> counter
    if (((state_counter >= _VAL_27000000_0) && (uart_ready == 1'b0))) begin
        state_counter_prod = state_counter_prod + state_counter;
    end
    // ((counter >= 27000000) && (uart_ready == 0)) : led -> led
    if (((state_counter >= _VAL_27000000_0) && (uart_ready == 1'b0))) begin
        state_led_prod = state_led_prod + state_led;
    end
    // (((counter >= 27000000) && (uart_ready == 1)) && (led == 0)) : 1 -> led
    if ((((state_counter >= _VAL_27000000_0) && (uart_ready == 1'b1)) && (state_led == 1'b0))) begin
        state_led_prod = state_led_prod + 1'b1;
    end
    // (((counter >= 27000000) && (uart_ready == 1)) && (led > 0)) : 0 -> led
    if ((((state_counter >= _VAL_27000000_0) && (uart_ready == 1'b1)) && (state_led > 1'b0))) begin
        state_led_prod = state_led_prod + 1'b0;
    end
    // ((counter >= 27000000) && (uart_ready == 1)) : 1 -> toggle_pulse
    if (((state_counter >= _VAL_27000000_0) && (uart_ready == 1'b1))) begin
        state_toggle_pulse_prod = state_toggle_pulse_prod + 1'b1;
    end

    state_counter_next = '0;
    state_counter_next = state_counter_next + state_counter_prod;
    state_led_next = '0;
    state_led_next = state_led_next + state_led_prod;
    state_toggle_pulse_next = '0;
    state_toggle_pulse_next = state_toggle_pulse_next + state_toggle_pulse_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset counter = 0.0
        state_counter <= _VAL_0_0;
        // reset led = 0.0
        state_led <= 1'b0;
        // reset toggle_pulse = 0.0
        state_toggle_pulse <= 1'b0;
    end else begin
        state_counter <= state_counter_next;
        state_led <= state_led_next;
        state_toggle_pulse <= state_toggle_pulse_next;
    end
end

assign led = conv_ufixed_40_10_to_logic(state_led);
assign uart_tx = uart_tx0__tx;

endmodule