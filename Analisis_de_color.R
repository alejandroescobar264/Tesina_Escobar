## Análisis de color

library(magick)
library(dplyr)
library(tidyr)
library(ggplot2)
library(stringr)
library(readr)

# Leer y limpiar CSV original
datos <- read_csv("Espécimenes - Modelos_3D.csv")
murcielagos <- datos %>% select(-Notas)

# Crear columna vacía para colores
murcielagos$Colores <- NA

# Crear carpeta de salida
dir.create("output", showWarnings = FALSE)

# Obtener archivos de imagen
img_files <- list.files("img/bg_removed", pattern = "\\.png$", full.names = TRUE)

# Procesar cada imagen
for (img_path in img_files) {
  
  # Leer imagen y nombre base
  img <- image_read(img_path)
  img_name <- tools::file_path_sans_ext(basename(img_path))  # p. ej., "A-147"
  
  # Escalar imagen
  img_small <- image_scale(img, "200")
  img_raster <- as.raster(img_small)
  rgb_matrix <- col2rgb(img_raster)
  
  # Convertir a data frame de colores
  pixels <- as.data.frame(t(rgb_matrix)) %>%
    rename(red = red, green = green, blue = blue) %>%
    filter(!(red > 250 & green > 250 & blue > 250))  # quitar fondo blanco
  
  # K-means
  set.seed(123)
  k <- 6
  kmeans_result <- kmeans(pixels, centers = k)
  colors <- as.data.frame(kmeans_result$centers)
  colors$hex <- rgb(colors$red, colors$green, colors$blue, maxColorValue = 255)
  colors$cluster <- 1:nrow(colors)
  pixels$cluster <- kmeans_result$cluster
  
  color_summary <- pixels %>%
    count(cluster) %>%
    left_join(colors, by = "cluster") %>%
    mutate(prop = n / sum(n)) %>%
    arrange(desc(prop))
  
  # Crear gráfico
  donut_plot <- ggplot(color_summary, aes(x = 2, y = prop, fill = hex)) +
    geom_bar(stat = "identity", width = 1, color = "white") +
    coord_polar(theta = "y") +
    xlim(0.5, 2.5) +  # ajusta el agujero central
    scale_fill_identity(name = "Color", labels = color_summary$hex, guide = "legend") +
    labs(
      title = img_name,
      subtitle = "Dominant Colors"
    ) +
    theme_void() +
    theme(
      legend.position = "bottom",
      legend.key.size = unit(2, "lines"),
      legend.text = element_text(size = 12),
      plot.title = element_text(hjust = 0.5, size = 20, margin = margin(b = 2)),
      plot.subtitle = element_text(hjust = 0.5, size = 15, margin = margin(b = 0)),
      plot.margin = unit(c(0.2, 0.2, 0, 0), "inches")  # reduce márgenes externos
    )
  
  # Guardar gráfico
  ggsave(
    filename = paste0("output/", img_name, "_colors.png"),
    plot = donut_plot,
    width = 6, height = 7
  )
  
  # Guardar colores en CSV
  hex_concat <- paste(color_summary$hex, collapse = ",")
  
  # Buscar fila correspondiente y asignar
  murcielagos$Colores[murcielagos$ID == img_name] <- hex_concat
}

write_csv(murcielagos, "murcielagos_colores.csv")