class item(str):
  def type(self):
    return self.split('__')[0]
  def id(self):
    return self.split('__')[1]
  def condition(self):
    return self.split('__')[2]
  def color(self):
    return self.split('__')[3]

  def set_condition(self, cond):
    my_words = self.split('__')
    my_words[2] = cond
    return "__".join(my_words)
