export function generatorSettings(
  outputType: string,
  values: {
    image_generator: string;
    image_model: string;
    video_generator: string;
    video_model: string;
  },
) {
  return outputType === "image"
    ? {
        image_generator: values.image_generator,
        image_model: values.image_model,
      }
    : { ...values };
}
