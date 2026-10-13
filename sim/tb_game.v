// testbench del juego con constantes chicas (ver Makefile, target sim)
// hace de "jugador": espera el led objetivo, aprieta despues de un rato
// y revisa lo que muestra el display
`timescale 1ns/1ps
module tb_game;
  reg clk = 0;
  always #20 clk = ~clk;             // 25 MHz

  reg  [3:0] btn = 4'b0;
  wire [3:0] led;
  wire [7:0] disp = dut.u_pochoco.u_periph.digit_q;

  game_top #(.MemFile("sim/game_sim.hex")) dut (.i_Clk(clk), .o_LED(led), .i_Switch(btn),
                .i_SPI_SCLK(1'b0), .i_SPI_MOSI(1'b0), .i_SPI_CS_n(1'b1));

  integer r, d, esperado, suma, errores, t_todos, n_todos, partida;
  reg [3:0] obj;

  function onehot(input [3:0] v);
    onehot = (v == 1) || (v == 2) || (v == 4) || (v == 8);
  endfunction

  function [7:0] bcd(input integer v);
    bcd = ((v / 10) * 16) + (v % 10);
  endfunction

  task apretar(input [3:0] b);
    begin
      btn = b;
      repeat (40) @(posedge clk);
      btn = 0;
    end
  endtask

  // espera hasta 3000 ciclos a que el display muestre v
  task esperar_display(input [7:0] v);
    integer k;
    begin
      k = 0;
      while (disp !== v && k < 3000) begin @(posedge clk); k = k + 1; end
      if (disp !== v) begin
        $display("\nERROR: display %h, esperaba %h", disp, v);
        errores = errores + 1;
      end
    end
  endtask

  initial begin
    $dumpfile("game.vcd");
    $dumpvars(0, tb_game);
    errores = 0;

    for (partida = 0; partida < 2; partida = partida + 1) begin
      // boton para empezar (en un momento distinto cada partida)
      repeat (1237 + partida * 3917) @(posedge clk);
      apretar(4'b0001);
      suma = 0;
      $write("partida %0d, leds objetivo:", partida);

      for (r = 0; r < 10; r = r + 1) begin
        // medir cuanto duran los 4 leds prendidos
        wait (led == 4'hF);
        n_todos = 0;
        while (led == 4'hF) begin @(posedge clk); n_todos = n_todos + 1; end
        if (n_todos < 3000) begin
          $display("\nERROR: fase de 4 leds duro %0d ciclos", n_todos); errores = errores + 1;
        end
        wait (onehot(led));
        obj = led;
        $write(" %0d", (obj == 1) ? 1 : (obj == 2) ? 2 : (obj == 4) ? 3 : 4);

        // en la ronda 4 de la primera partida se aprieta mal primero
        if (partida == 0 && r == 3) begin
          repeat (150) @(posedge clk);
          apretar(obj == 4'b1000 ? 4'b0001 : obj + obj);
          repeat (20) @(posedge clk);
          if (disp !== 8'hEE) begin
            $display("\nERROR: no mostro EE"); errores = errores + 1;
          end
          $write("(EE)");
          wait (led == 4'hF);          // se repite la ronda
          wait (onehot(led));
          obj = led;
          $write(" %0d", (obj == 1) ? 1 : (obj == 2) ? 2 : (obj == 4) ? 3 : 4);
        end

        // tiempo de reaccion: (r+1)*130 + 20 ciclos -> decimas = /100
        d = (r + 1) * 130 + 20 + partida * 300;
        repeat (d) @(posedge clk);
        apretar(obj);
        esperado = d / 100;
        suma = suma + esperado;
        esperar_display(bcd(esperado));
      end

      // promedio redondeado
      esperado = (suma + 5) / 10;
      esperar_display(bcd(esperado));
      $display("\n  promedio en display = %h (esperado %h)", disp, bcd(esperado));
      // los leds tienen que parpadear
      wait (led == 4'h0); wait (led == 4'hF);
      $display("  leds parpadeando ok");
    end

    if (errores == 0) $display("TODO OK");
    else $display("FALLARON %0d CHEQUEOS", errores);
    $finish;
  end

  initial begin
    #50000000 $display("TIMEOUT"); $finish;
  end
endmodule
